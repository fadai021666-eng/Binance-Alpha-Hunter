"""发现打分相关逻辑。"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from ..types import AlphaCandidate
from .scoring_config import (
    ILLIQUID_THRESHOLDS,
    NEW_LISTING_WATCH_ONLY_PERCENTILE,
    OVERHEATED_THRESHOLDS,
    SCORE_CONFIG,
    SYNCHRONIZED_EXPANSION_THRESHOLDS,
)


DISCOVER_MODES = {"momentum", "safe", "early", "contrarian"}


def _safe_round(value: float, digits: int = 8) -> float:
    return round(float(value), digits)


def compute_kline_metrics(klines: list[list[Any]]) -> dict[str, float | bool]:
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[float] = []
    for row in klines:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            highs.append(float(row[2]))
            lows.append(float(row[3]))
            closes.append(float(row[4]))
            volumes.append(float(row[5]))
        except (TypeError, ValueError):
            continue

    if not closes:
        return {
            "latest_close": 0.0,
            "return_5m": 0.0,
            "return_15m": 0.0,
            "avg_volume_5": 0.0,
            "avg_volume_20": 0.0,
            "last_volume": 0.0,
            "recent_high_20": 0.0,
            "recent_low_20": 0.0,
            "volume_spike": False,
            "price_breakout": False,
        }

    def _return_from_lookback(lookback: int) -> float:
        if len(closes) <= lookback:
            return 0.0
        prev = closes[-lookback - 1]
        if prev <= 0:
            return 0.0
        return (closes[-1] - prev) / prev

    recent_high_20 = max(highs[-20:]) if highs else closes[-1]
    recent_low_20 = min(lows[-20:]) if lows else closes[-1]
    avg_volume_5 = statistics.fmean(volumes[-5:]) if volumes else 0.0
    avg_volume_20 = statistics.fmean(volumes[-20:]) if volumes else 0.0
    last_volume = volumes[-1] if volumes else 0.0
    return_5m = _return_from_lookback(5)
    return_15m = _return_from_lookback(15)
    volume_spike = bool(
        avg_volume_20 > 0
        and (last_volume >= avg_volume_20 * 1.8 or avg_volume_5 >= avg_volume_20 * 1.45)
    )
    price_breakout = bool(
        recent_high_20 > 0
        and closes[-1] >= recent_high_20 * 0.995
        and return_5m >= 0.008
    )
    return {
        "latest_close": closes[-1],
        "return_5m": return_5m,
        "return_15m": return_15m,
        "avg_volume_5": avg_volume_5,
        "avg_volume_20": avg_volume_20,
        "last_volume": last_volume,
        "recent_high_20": recent_high_20,
        "recent_low_20": recent_low_20,
        "volume_spike": volume_spike,
        "price_breakout": price_breakout,
    }


def _percentile_rank(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    count = sum(1 for current in sorted_values if value >= current)
    return count / len(sorted_values)


def _is_new_listing(candidate: AlphaCandidate) -> bool:
    if not candidate.listing_time_ms:
        return False
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    age_ms = max(0, now_ms - candidate.listing_time_ms)
    return age_ms <= 72 * 60 * 60 * 1000


def _build_discover_tags(
    candidate: AlphaCandidate,
    metrics: dict[str, float | bool],
    volume_percentile: float,
    is_new: bool,
    illiquid: bool,
    overheated: bool,
    watch_only: bool,
) -> list[str]:
    tags = {"candidate"}
    if "热门" in candidate.tags or volume_percentile >= 0.85:
        tags.add("hot")
    if is_new:
        tags.add("new")
    if metrics["volume_spike"]:
        tags.add("volume_spike")
    if metrics["price_breakout"]:
        tags.add("price_breakout")
    if illiquid:
        tags.add("illiquid")
    if overheated:
        tags.add("overheated")
    if watch_only:
        tags.add("watch_only")
    ordered = [
        "hot",
        "new",
        "volume_spike",
        "price_breakout",
        "illiquid",
        "overheated",
        "watch_only",
        "candidate",
    ]
    return [tag for tag in ordered if tag in tags]


def _mode_match(mode: str, candidate: AlphaCandidate, metrics: dict[str, float | bool], illiquid: bool, overheated: bool, is_new: bool) -> bool:
    change_24h = candidate.change_24h
    if mode == "momentum":
        return (change_24h >= 3 or metrics["volume_spike"] or metrics["price_breakout"]) and not illiquid
    if mode == "safe":
        return not illiquid and not overheated and abs(change_24h) <= 25
    if mode == "early":
        return is_new or metrics["volume_spike"] or metrics["price_breakout"]
    if mode == "contrarian":
        return -30 <= change_24h <= -5 and not illiquid
    return True


def _build_discover_reason(
    mode: str,
    candidate: AlphaCandidate,
    metrics: dict[str, float | bool],
    volume_percentile: float,
    is_new: bool,
    illiquid: bool,
    overheated: bool,
    watch_only: bool,
) -> tuple[str, list[str]]:
    explain: list[str] = []
    if volume_percentile >= 0.85:
        explain.append("24 小时成交量位于当前 Alpha 候选前列。")
    elif volume_percentile >= 0.6:
        explain.append("24 小时成交量处于中上水平。")

    if metrics["volume_spike"] and metrics["price_breakout"]:
        explain.append("短线出现量价同步放大，并且接近突破位。")
    elif metrics["volume_spike"]:
        explain.append("短线成交量明显放大。")
    elif metrics["price_breakout"]:
        explain.append("价格正在靠近短线突破位。")

    if is_new:
        explain.append("属于相对较新的 Alpha 标的。")
    if illiquid:
        explain.append("流动性偏弱，滑点风险更高。")
    if overheated:
        explain.append("短线过热，追高容错率较低。")
    if candidate.change_24h <= -8 and mode == "contrarian":
        explain.append("经历明显回撤，适合反向观察而不是追涨。")
    if watch_only:
        explain.append("更适合先观察，不适合直接激进参与。")

    if mode == "momentum":
        if metrics["volume_spike"] and metrics["price_breakout"]:
            reason = "量价同步放大，适合动量观察。"
        elif candidate.change_24h >= 8:
            reason = "24 小时涨幅和成交量都不弱，具备动量特征。"
        else:
            reason = "具备一定动量特征，但需要继续看承接。"
    elif mode == "safe":
        if not illiquid and not overheated:
            reason = "流动性和热度相对可控，更适合稳健观察。"
        else:
            reason = "虽然进入候选，但更适合先观察风险。"
    elif mode == "early":
        if is_new:
            reason = "新标的特征明显，适合早期跟踪。"
        else:
            reason = "尚处于早期放量阶段，适合提前盯盘。"
    else:
        reason = "经历回撤但未完全失去成交，适合反向观察。"

    if not explain:
        explain.append("当前样本中相对更符合该模式。")

    return reason, explain[:4]


def _mode_score_adjustment(
    mode: str,
    candidate: AlphaCandidate,
    metrics: dict[str, float | bool],
    is_new: bool,
    illiquid: bool,
    overheated: bool,
) -> int:
    change_24h = candidate.change_24h
    bonus = 0
    if mode == "momentum":
        if change_24h >= 8:
            bonus += 12
        if metrics["price_breakout"]:
            bonus += 8
        if metrics["volume_spike"]:
            bonus += 8
        if change_24h < 0:
            bonus -= 12
    elif mode == "safe":
        if not illiquid and not overheated:
            bonus += 14
        if abs(change_24h) <= 15:
            bonus += 8
        if is_new:
            bonus -= 8
    elif mode == "early":
        if is_new:
            bonus += 16
        if metrics["volume_spike"]:
            bonus += 10
        if metrics["price_breakout"]:
            bonus += 6
    elif mode == "contrarian":
        if -25 <= change_24h <= -6:
            bonus += 16
        if float(metrics["return_5m"]) >= -0.01:
            bonus += 8
        if change_24h > 10:
            bonus -= 14
    if illiquid:
        bonus -= 10
    if overheated:
        bonus -= 10
    return bonus


def build_discover_candidates(
    candidates: list[AlphaCandidate],
    candidate_klines: dict[str, list[list[Any]]],
    mode: str,
) -> list[dict[str, Any]]:
    if mode not in DISCOVER_MODES:
        raise ValueError(f"unsupported discover mode: {mode}")

    volume_values = [candidate.volume_24h for candidate in candidates]
    liquidity_values = [candidate.liquidity for candidate in candidates]
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        metrics = compute_kline_metrics(candidate_klines.get(candidate.symbol, []))
        volume_percentile = _percentile_rank(candidate.volume_24h, volume_values)
        liquidity_percentile = _percentile_rank(candidate.liquidity, liquidity_values)
        is_new = _is_new_listing(candidate)
        synchronized_expansion = bool(
            metrics["volume_spike"]
            and (
                candidate.change_24h >= SYNCHRONIZED_EXPANSION_THRESHOLDS["min_change_24h"]
                or float(metrics["return_15m"]) >= SYNCHRONIZED_EXPANSION_THRESHOLDS["min_return_15m"]
            )
        )
        illiquid = bool(
            candidate.liquidity < ILLIQUID_THRESHOLDS["min_liquidity"]
            or liquidity_percentile <= ILLIQUID_THRESHOLDS["min_liquidity_percentile"]
            or candidate.volume_24h < ILLIQUID_THRESHOLDS["min_volume"]
        )
        overheated = bool(
            candidate.change_24h >= OVERHEATED_THRESHOLDS["max_change_24h"]
            or (float(metrics["return_5m"]) >= OVERHEATED_THRESHOLDS["max_return_5m_with_spike"] and metrics["volume_spike"])
        )
        watch_only = bool(illiquid or overheated or (is_new and liquidity_percentile < NEW_LISTING_WATCH_ONLY_PERCENTILE))

        score = SCORE_CONFIG["base_score"]
        change_ranges = SCORE_CONFIG["change_24h"]
        ch = candidate.change_24h
        if change_ranges["strong_up"]["range"][0] <= ch <= change_ranges["strong_up"]["range"][1]:
            score += change_ranges["strong_up"]["bonus"]
        elif change_ranges["very_strong_up"]["range"][0] < ch <= change_ranges["very_strong_up"]["range"][1]:
            score += change_ranges["very_strong_up"]["bonus"]
        elif change_ranges["weak_up"]["range"][0] < ch < change_ranges["weak_up"]["range"][1]:
            score += change_ranges["weak_up"]["bonus"]
        elif change_ranges["mild_down"]["range"][0] <= ch < change_ranges["mild_down"]["range"][1]:
            score += change_ranges["mild_down"]["bonus"]
        elif ch < change_ranges["deep_down"]["range"][1]:
            score += change_ranges["deep_down"]["bonus"]

        score += int(volume_percentile * SCORE_CONFIG["volume_percentile_weight"])
        if synchronized_expansion:
            score += SCORE_CONFIG["synchronized_expansion_bonus"]
        if is_new:
            score += SCORE_CONFIG["new_listing_bonus"]
        if metrics["price_breakout"]:
            score += SCORE_CONFIG["price_breakout_bonus"]
        if illiquid:
            score += SCORE_CONFIG["illiquid_penalty"]
        if overheated:
            score += SCORE_CONFIG["overheated_penalty"]
        if float(metrics["return_5m"]) < SCORE_CONFIG["short_term_dump_threshold"]:
            score += SCORE_CONFIG["short_term_dump_penalty"]
        score += _mode_score_adjustment(mode, candidate, metrics, is_new, illiquid, overheated)
        score = max(0, min(score, 100))

        reason, explain = _build_discover_reason(
            mode,
            candidate,
            metrics,
            volume_percentile,
            is_new,
            illiquid,
            overheated,
            watch_only,
        )
        tags = _build_discover_tags(
            candidate,
            metrics,
            volume_percentile,
            is_new,
            illiquid,
            overheated,
            watch_only,
        )

        results.append(
            {
                "symbol": candidate.symbol,
                "price": _safe_round(candidate.price, 8),
                "24h_change": _safe_round(candidate.change_24h, 4),
                "volume_24h": _safe_round(candidate.volume_24h, 2),
                "liquidity": _safe_round(candidate.liquidity, 2),
                "tags": tags,
                "opportunity_score": score,
                "reason": reason,
                "explain": explain,
                "mode_match": _mode_match(mode, candidate, metrics, illiquid, overheated, is_new),
            }
        )
    return results
