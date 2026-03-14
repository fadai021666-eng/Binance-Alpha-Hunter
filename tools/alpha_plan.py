#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PAPER_TRADES_PATH = DATA_DIR / "paper_trades.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.binance_alpha import BinanceAlphaError, get_candidate_snapshot, list_alpha_candidates  # noqa: E402
from lib.rules import build_discover_candidates, build_risk_report, build_trade_plan  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 Binance Alpha 交易计划或执行 paper trade")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="生成交易计划")
    plan_parser.add_argument("symbol", help="目标标的")
    plan_parser.add_argument(
        "--style",
        choices=["conservative", "balanced", "aggressive"],
        default="balanced",
        help="交易风格",
    )
    plan_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")

    execute_parser = subparsers.add_parser("execute", help="执行占位交易")
    execute_parser.add_argument("symbol", help="目标标的")
    execute_parser.add_argument("--side", choices=["buy", "sell"], default="buy", help="方向")
    execute_parser.add_argument("--amount-usd", type=float, default=100.0, help="名义资金")
    execute_parser.add_argument(
        "--style",
        choices=["conservative", "balanced", "aggressive"],
        default="balanced",
        help="计划风格",
    )
    execute_parser.add_argument(
        "--mode",
        choices=["paper", "spot", "futures"],
        default="paper",
        help="执行模式，MVP 默认只支持 paper",
    )
    execute_parser.add_argument("--confirm", action="store_true", help="明确确认执行")
    execute_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")

    history_parser = subparsers.add_parser("history", help="查看 paper trade 历史")
    history_parser.add_argument("--symbol", default="", help="按 symbol 过滤")
    history_parser.add_argument("--limit", type=int, default=None, help="最近 N 条")
    history_parser.add_argument("--summary", action="store_true", help="输出快速摘要")
    history_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")
    return parser


def _load_paper_trades() -> list[dict]:
    if not PAPER_TRADES_PATH.exists():
        return []
    return json.loads(PAPER_TRADES_PATH.read_text(encoding="utf-8"))


def _save_paper_trades(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PAPER_TRADES_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _render(payload: dict, raw: bool) -> str:
    if raw:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _build_recent_trade_summary(records: list[dict]) -> dict | None:
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


def _normalize_trade_record(record: dict, index: int) -> dict:
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


def _load_normalized_paper_trades() -> list[dict]:
    raw_items = _load_paper_trades()
    items = [_normalize_trade_record(item, index) for index, item in enumerate(raw_items)]
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return items


def _build_history_payload(symbol: str, limit: int | None, summary: bool) -> dict:
    records = _load_normalized_paper_trades()
    normalized_symbol = _normalize_symbol(symbol) if symbol else ""
    if normalized_symbol:
        records = [item for item in records if _normalize_symbol(str(item.get("symbol") or "")) == normalized_symbol]
    if limit is not None:
        records = records[: max(limit, 0)]

    quick_summary = (
        f"当前共命中 {len(records)} 条 paper trade 记录。"
        if records
        else "当前没有符合条件的 paper trade 记录。"
    )
    if records:
        latest = records[0]
        quick_summary = (
            f"当前共命中 {len(records)} 条 paper trade 记录，"
            f"最近一条是 {latest.get('symbol')} / {latest.get('action')} / {latest.get('style')}。"
        )

    payload = {
        "intent": "paper_trade_history",
        "count": len(records),
        "filters": {
            "symbol": symbol or None,
            "limit": limit,
        },
        "quick_summary": quick_summary,
        "recent_trade_summary": _build_recent_trade_summary(records),
    }

    if summary:
        payload["items"] = [
            {
                "trade_id": item.get("trade_id"),
                "symbol": item.get("symbol"),
                "action": item.get("action"),
                "created_at": item.get("created_at"),
                "execution_summary": item.get("execution_summary"),
            }
            for item in records
        ]
    else:
        payload["items"] = records
    return payload


def _build_plan_context(symbol: str, style: str) -> dict:
    snapshot = get_candidate_snapshot(symbol)
    risk_report = build_risk_report(
        snapshot["candidate"],
        snapshot["meta"],
        snapshot["klines"],
        snapshot["book_ticker"],
    )
    candidates = list_alpha_candidates(limit=None, sort_by="volume")
    discover_items = build_discover_candidates(
        candidates,
        {snapshot["candidate"].symbol: snapshot["klines"]},
        mode="momentum",
    )
    discover_map = {item["symbol"]: item for item in discover_items}
    discover_item = discover_map.get(
        snapshot["candidate"].symbol,
        {
            "opportunity_score": None,
            "tags": [],
            "reason": "",
            "explain": [],
        },
    )
    plan = build_trade_plan(risk_report, style)
    plan["intent"] = "make_trade_plan"
    plan["risk_report"] = {
        "volatility_risk": risk_report["volatility_risk"],
        "liquidity_risk": risk_report["liquidity_risk"],
        "beginner_friendly": risk_report["beginner_friendly"],
        "suggested_mode": risk_report["suggested_mode"],
        "risk_flags": risk_report["risk_flags"],
    }
    plan["data_source"] = snapshot["fetch_meta"]["data_source"]
    plan["stale"] = snapshot["fetch_meta"]["stale"]
    plan["fetch_warnings"] = snapshot["fetch_meta"]["fetch_warnings"]
    plan["recent_trade_summary"] = _build_recent_trade_summary(
        [
            item
            for item in _load_normalized_paper_trades()
            if _normalize_symbol(str(item.get("symbol") or "")) == _normalize_symbol(plan["symbol"])
        ]
    )
    return {
        "plan": plan,
        "risk_report": risk_report,
        "discover_item": discover_item,
    }


def _make_plan(symbol: str, style: str) -> dict:
    return _build_plan_context(symbol, style)["plan"]


def _execute(symbol: str, side: str, amount_usd: float, style: str, mode: str, confirm: bool) -> dict:
    context = _build_plan_context(symbol, style)
    plan = context["plan"]
    risk_report = context["risk_report"]
    discover_item = context["discover_item"]
    payload = {
        "intent": "execute_trade",
        "symbol": plan["symbol"],
        "side": side,
        "amount_usd": round(amount_usd, 2),
        "mode": mode,
        "plan": {
            "entry": plan["entry"],
            "stop_loss": plan["stop_loss"],
            "take_profit": plan["take_profit"],
            "position_size": plan["position_size"],
            "invalidation": plan["invalidation"],
            "confidence": plan["confidence"],
            "plan_reason": plan["plan_reason"],
        },
        "data_source": plan.get("data_source"),
        "stale": plan.get("stale"),
        "fetch_warnings": plan.get("fetch_warnings"),
    }

    if not confirm:
        payload["status"] = "needs_confirmation"
        payload["message"] = "默认不直接交易。只有用户明确确认后，才允许 execute_trade。"
        return payload

    if mode != "paper":
        payload["status"] = "not_implemented"
        payload["message"] = "MVP 当前只支持 paper trade，占位保留了 Spot / Futures 接口。"
        return payload

    items = _load_paper_trades()
    created_at = datetime.now(timezone.utc).isoformat()
    trade_id = f"paper-{created_at.replace(':', '').replace('-', '').replace('.', '')}-{uuid4().hex[:8]}"
    execution_summary = (
        f"{plan['symbol']} 的 paper trade 已记录，"
        f"方向 {side}，风格 {style}，"
        f"信心 {plan.get('confidence')}，"
        f"原因：{plan.get('plan_reason')}"
    )
    record = {
        "trade_id": trade_id,
        "symbol": plan["symbol"],
        "style": style,
        "action": side,
        "side": side,
        "amount_usd": round(amount_usd, 2),
        "mode": mode,
        "created_at": created_at,
        "entry": plan["entry"],
        "stop_loss": plan["stop_loss"],
        "take_profit": plan["take_profit"],
        "position_size": plan["position_size"],
        "invalidation": plan["invalidation"],
        "confidence": plan["confidence"],
        "plan_reason": plan["plan_reason"],
        "risk_report": risk_report,
        "risk_flags": risk_report["risk_flags"],
        "suggested_mode": risk_report["suggested_mode"],
        "opportunity_score": discover_item.get("opportunity_score"),
        "tags": discover_item.get("tags") or [],
        "execution_summary": execution_summary,
    }
    items.append(record)
    _save_paper_trades(items)

    payload["status"] = "paper_executed"
    payload["message"] = "已记录到 paper trade 日志。"
    payload["record"] = _normalize_trade_record(record, len(items) - 1)
    payload["paper_trade_count"] = len(items)
    payload["recent_trade_summary"] = _build_recent_trade_summary(_load_normalized_paper_trades())
    return payload


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "plan":
            payload = _make_plan(args.symbol, args.style)
            print(_render(payload, args.raw))
            return 0

        if args.command == "history":
            payload = _build_history_payload(args.symbol, args.limit, args.summary)
            print(_render(payload, args.raw))
            return 0

        payload = _execute(args.symbol, args.side, args.amount_usd, args.style, args.mode, args.confirm)
        print(_render(payload, args.raw))
        return 0 if payload.get("status") != "not_implemented" else 1
    except BinanceAlphaError as exc:
        payload = {
            "intent": "execute_trade" if args.command == "execute" else "make_trade_plan",
            "status": "error",
            "message": str(exc),
        }
        print(_render(payload, getattr(args, "raw", False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
