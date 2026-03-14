#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.binance_alpha import BinanceAlphaError, resolve_candidate  # noqa: E402
from lib.output import render  # noqa: E402
from lib.watchlist import (  # noqa: E402
    build_watchlist_compare_snapshot,
    load_watchlist,
    save_watchlist,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 Binance Alpha watchlist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="添加 watchlist")
    add_parser.add_argument("symbol", help="目标标的")
    add_parser.add_argument("--note", default="", help="备注")
    add_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")

    remove_parser = subparsers.add_parser("remove", help="移除 watchlist")
    remove_parser.add_argument("symbol", help="目标标的")
    remove_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")

    list_parser = subparsers.add_parser("list", help="列出 watchlist")
    list_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")

    compare_parser = subparsers.add_parser("compare", help="对比 watchlist 当前结果与上次快照")
    compare_parser.add_argument(
        "--mode",
        choices=["momentum", "safe", "early", "contrarian"],
        default="momentum",
        help="对比时采用的 hunter 模式",
    )
    compare_parser.add_argument("--summary", action="store_true", help="输出快速摘要")
    compare_parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    items = load_watchlist()

    if args.command == "list":
        payload = {
            "intent": "watchlist_list",
            "count": len(items),
            "items": items,
        }
        print(render(payload, args.raw))
        return 0

    if args.command == "compare":
        payload = build_watchlist_compare_snapshot(args.mode, persist=True)
        if payload is None:
            payload = {
                "intent": "watchlist_compare",
                "mode": args.mode,
                "compare_at": datetime.now(timezone.utc).isoformat(),
                "count": 0,
                "status_counts": {
                    "new": 0,
                    "improving": 0,
                    "weakening": 0,
                    "tags_changed": 0,
                    "stable": 0,
                    "missing": 0,
                },
                "quick_summary": "当前没有可比较的 watchlist 历史。",
                "highlights": {
                    "top_improving": None,
                    "top_weakening": None,
                    "improving_symbols": [],
                    "weakening_symbols": [],
                    "turned_watch_only": [],
                },
                "items": [],
            }
        if args.summary:
            payload["items"] = [
                {
                    "symbol": item["symbol"],
                    "status_change": item["status_change"],
                    "summary": item["summary"],
                }
                for item in payload["items"]
            ]
        print(render(payload, args.raw))
        return 0

    try:
        candidate = resolve_candidate(args.symbol)
    except BinanceAlphaError as exc:
        payload = {
            "intent": f"watchlist_{args.command}",
            "status": "error",
            "message": str(exc),
        }
        print(render(payload, getattr(args, "raw", False)))
        return 1

    if args.command == "add":
        existing = next((item for item in items if item.get("symbol") == candidate.symbol), None)
        if existing:
            existing["note"] = args.note or existing.get("note", "")
            existing["updated_at"] = datetime.now(timezone.utc).isoformat()
            status = "updated"
            entry = existing
        else:
            entry = {
                "symbol": candidate.symbol,
                "token_symbol": candidate.token_symbol,
                "market_symbol": candidate.market_symbol,
                "chain_name": candidate.chain_name,
                "price": round(candidate.price, 8),
                "tags": candidate.tags,
                "note": args.note,
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
            items.append(entry)
            status = "added"

        save_watchlist(items)
        payload = {
            "intent": "watchlist_add",
            "status": status,
            "item": entry,
            "count": len(items),
        }
        print(render(payload, args.raw))
        return 0

    filtered = [item for item in items if item.get("symbol") != candidate.symbol]
    removed = len(filtered) != len(items)
    save_watchlist(filtered)
    payload = {
        "intent": "watchlist_remove",
        "status": "removed" if removed else "not_found",
        "symbol": candidate.symbol,
        "count": len(filtered),
    }
    print(render(payload, args.raw))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
