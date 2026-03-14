"""Paper trade 持久化与摘要构建。"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PAPER_TRADES_PATH = DATA_DIR / "paper_trades.json"


def load_paper_trades() -> list[dict]:
    if not PAPER_TRADES_PATH.exists():
        return []
    return json.loads(PAPER_TRADES_PATH.read_text(encoding="utf-8"))


def save_paper_trades(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PAPER_TRADES_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_trade_record(record: dict, index: int) -> dict:
    risk_report = record.get("risk_report") or {}
    if not isinstance(risk_report, dict):
        risk_report = {}
    risk_flags = record.get("risk_flags") or risk_report.get("risk_flags") or []
    if not isinstance(risk_flags, list):
        risk_flags = []
    entry = record.get("entry") or {}
    position_size = record.get("position_size") or {}
    action = record.get("action") or record.get("side") or "buy"
    style = record.get("style") or "balanced"
    symbol = record.get("symbol") or ""
    created_at = record.get("created_at") or ""
    execution_summary = record.get("execution_summary")
    if not execution_summary:
        execution_summary = (
            f"{symbol} 的 paper trade 已记录，"
            f"方向 {action}，风格 {style}。"
        )
    return {
        "trade_id": record.get("trade_id") or f"legacy-{index + 1}",
        "symbol": symbol,
        "style": style,
        "action": action,
        "amount_usd": record.get("amount_usd"),
        "mode": record.get("mode", "paper"),
        "created_at": created_at,
        "entry": entry,
        "stop_loss": record.get("stop_loss"),
        "take_profit": record.get("take_profit"),
        "position_size": position_size,
        "invalidation": record.get("invalidation"),
        "confidence": record.get("confidence"),
        "plan_reason": record.get("plan_reason"),
        "risk_report": risk_report,
        "risk_flags": risk_flags,
        "suggested_mode": record.get("suggested_mode") or risk_report.get("suggested_mode"),
        "opportunity_score": record.get("opportunity_score"),
        "tags": record.get("tags") or [],
        "execution_summary": execution_summary,
    }


def load_normalized_paper_trades() -> list[dict]:
    raw_items = load_paper_trades()
    items = [normalize_trade_record(item, index) for index, item in enumerate(raw_items)]
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return items


def build_recent_trade_summary(records: list[dict]) -> dict | None:
    if not records:
        return None
    latest = records[0]
    symbol_counts: dict[str, int] = {}
    for record in records:
        symbol = str(record.get("symbol") or "")
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
    top_symbols = sorted(symbol_counts.items(), key=lambda item: item[1], reverse=True)[:3]
    return {
        "latest_trade_id": latest.get("trade_id"),
        "latest_symbol": latest.get("symbol"),
        "latest_style": latest.get("style"),
        "latest_action": latest.get("action"),
        "latest_created_at": latest.get("created_at"),
        "latest_confidence": latest.get("confidence"),
        "latest_plan_reason": latest.get("plan_reason"),
        "latest_risk_summary": (latest.get("risk_report") or {}).get("risk_summary"),
        "latest_execution_summary": latest.get("execution_summary"),
        "symbol": latest.get("symbol"),
        "style": latest.get("style"),
        "action": latest.get("action"),
        "created_at": latest.get("created_at"),
        "confidence": latest.get("confidence"),
        "plan_reason": latest.get("plan_reason"),
        "risk_summary": (latest.get("risk_report") or {}).get("risk_summary"),
        "execution_summary": latest.get("execution_summary"),
        "top_symbols": [{"symbol": symbol, "count": count} for symbol, count in top_symbols],
    }
