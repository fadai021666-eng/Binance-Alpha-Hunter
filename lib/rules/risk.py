"""风险评估相关逻辑。"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from ..types import AlphaCandidate


def _safe_round(value: float, digits: int = 8) -> float:
    return round(float(value), digits)


def compute_volatility(klines: list[list[Any]]) -> float:
    closes: list[float] = []
    for row in klines:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            closes.append(float(row[4]))
        except (TypeError, ValueError):
            continue

    if len(closes) < 2:
        return 0.0

    returns = [
        (next_price - prev_price) / prev_price
        for prev_price, next_price in zip(closes, closes[1:])
        if prev_price > 0
    ]
    if not returns:
        return 0.0
    if len(returns) == 1:
        return abs(returns[0])
    return statistics.pstdev(returns)


def compute_relative_spread(book_ticker: dict[str, Any]) -> float:
    try:
        bid = float(book_ticker.get("bidPrice") or 0.0)
        ask = float(book_ticker.get("askPrice") or 0.0)
    except (TypeError, ValueError):
        return 0.0

    if bid <= 0 or ask <= 0:
        return 0.0
    mid = (bid + ask) / 2
    if mid <= 0:
        return 0.0
    return (ask - bid) / mid


def _volatility_level(volatility: float) -> str:
    if volatility < 0.006:
        return "low"
    if volatility < 0.015:
        return "medium"
    return "high"


def _liquidity_level(candidate: AlphaCandidate) -> str:
    if candidate.liquidity >= 2_000_000 and candidate.volume_24h >= 5_000_000:
        return "low"
    if candidate.liquidity >= 500_000 and candidate.volume_24h >= 1_000_000:
        return "medium"
    return "high"


def _beginner_friendly(
    volatility_level: str,
    liquidity_level: str,
    spread: float,
    change_24h: float,
) -> bool:
    return (
        volatility_level == "low"
        and liquidity_level != "high"
        and spread < 0.004
        and abs(change_24h) < 25
    )


def _suggested_mode(volatility_level: str, liquidity_level: str, beginner_friendly: bool) -> str:
    if beginner_friendly:
        return "conservative"
    if volatility_level == "high" or liquidity_level == "high":
        return "aggressive"
    return "balanced"


def _risk_score(volatility_level: str, liquidity_level: str, spread: float, change_24h: float) -> int:
    score = 0
    score += {"low": 10, "medium": 25, "high": 45}[volatility_level]
    score += {"low": 10, "medium": 20, "high": 35}[liquidity_level]
    score += 10 if spread >= 0.01 else 5 if spread >= 0.004 else 0
    score += 10 if abs(change_24h) >= 40 else 5 if abs(change_24h) >= 15 else 0
    return min(score, 100)


def _risk_notes(
    candidate: AlphaCandidate,
    volatility_level: str,
    liquidity_level: str,
    spread: float,
    beginner_friendly: bool,
) -> list[str]:
    notes: list[str] = []
    if volatility_level == "high":
        notes.append("分钟级波动偏大，容易出现追涨杀跌。")
    elif volatility_level == "medium":
        notes.append("短线波动不低，更适合分批观察而不是一次性重仓。")
    else:
        notes.append("短线波动相对可控。")

    if liquidity_level == "high":
        notes.append("流动性偏弱，成交滑点和冲击成本需要额外注意。")
    elif liquidity_level == "medium":
        notes.append("流动性中等，适合中小仓位。")
    else:
        notes.append("流动性相对健康。")

    if spread >= 0.01:
        notes.append("盘口价差偏大，挂单和止损要保守。")
    elif spread >= 0.004:
        notes.append("盘口价差中等，避免市价追单。")

    if abs(candidate.change_24h) >= 40:
        notes.append("24 小时振幅或涨跌幅过大，不适合新手冲动参与。")

    if beginner_friendly:
        notes.append("对新手相对友好，但仍建议小仓位试探。")
    else:
        notes.append("不建议新手直接重仓参与。")

    return notes


def _risk_flags(
    candidate: AlphaCandidate,
    volatility_level: str,
    liquidity_level: str,
    spread: float,
    beginner_friendly: bool,
) -> list[str]:
    flags: list[str] = []
    if volatility_level == "high":
        flags.append("high_volatility")
    if liquidity_level == "high":
        flags.append("illiquid")
    if spread >= 0.01:
        flags.append("wide_spread")
    elif spread >= 0.004:
        flags.append("spread_sensitive")
    if candidate.change_24h >= 40:
        flags.append("overheated")
    elif candidate.change_24h <= -25:
        flags.append("deep_pullback")
    if not beginner_friendly:
        flags.append("not_beginner_friendly")
    return flags


def build_risk_report(
    candidate: AlphaCandidate,
    meta: dict[str, Any],
    klines: list[list[Any]],
    book_ticker: dict[str, Any],
) -> dict[str, Any]:
    volatility = compute_volatility(klines)
    spread = compute_relative_spread(book_ticker)
    vol_level = _volatility_level(volatility)
    liq_level = _liquidity_level(candidate)
    beginner = _beginner_friendly(vol_level, liq_level, spread, candidate.change_24h)
    suggested = _suggested_mode(vol_level, liq_level, beginner)
    risk_sc = _risk_score(vol_level, liq_level, spread, candidate.change_24h)

    links = [
        item.get("link")
        for item in (meta.get("links") or [])
        if isinstance(item, dict) and item.get("link")
    ]
    notes = _risk_notes(candidate, vol_level, liq_level, spread, beginner)
    flags = _risk_flags(candidate, vol_level, liq_level, spread, beginner)

    return {
        "symbol": candidate.symbol,
        "risk_score": risk_sc,
        "key_info": {
            "symbol": candidate.symbol,
            "token_symbol": candidate.token_symbol,
            "name": candidate.name,
            "price": _safe_round(candidate.price, 8),
            "24h_change": _safe_round(candidate.change_24h, 4),
            "volume_24h": _safe_round(candidate.volume_24h, 2),
            "liquidity": _safe_round(candidate.liquidity, 2),
            "market_cap": _safe_round(candidate.market_cap, 2),
            "fdv": _safe_round(candidate.fdv, 2),
            "holders": candidate.holders,
            "chain": candidate.chain_name,
            "chain_id": candidate.chain_id,
            "contract_address": candidate.contract_address,
            "alpha_id": candidate.alpha_id,
            "market_symbol": candidate.market_symbol,
            "tags": candidate.tags,
            "links": links,
        },
        "market_state": {
            "minute_volatility": _safe_round(volatility, 6),
            "relative_spread": _safe_round(spread, 6),
            "best_bid": _safe_round(float(book_ticker.get("bidPrice") or 0.0), 8),
            "best_ask": _safe_round(float(book_ticker.get("askPrice") or 0.0), 8),
        },
        "volatility_risk": vol_level,
        "liquidity_risk": liq_level,
        "beginner_friendly": beginner,
        "suggested_mode": suggested,
        "risk_flags": flags,
        "risk_summary": (
            f"{candidate.symbol} 当前波动风险为 {vol_level}，"
            f"流动性风险为 {liq_level}，"
            f"更适合 {suggested} 风格。"
        ),
        "notes": notes,
        "meta_excerpt": {
            "description": meta.get("description"),
            "creator_address": meta.get("creatorAddress"),
            "audit_info": meta.get("auditInfo"),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
