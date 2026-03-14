#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.binance_alpha import BinanceAlphaError, get_candidate_snapshot  # noqa: E402
from lib.rules import build_risk_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="输出单个 Binance Alpha 标的的风险摘要")
    parser.add_argument("symbol", help="symbol / token symbol / alpha id / market symbol / contract")
    parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        snapshot = get_candidate_snapshot(args.symbol)
        payload = build_risk_report(
            snapshot["candidate"],
            snapshot["meta"],
            snapshot["klines"],
            snapshot["book_ticker"],
        )
        payload["intent"] = "get_risk_report"
        payload["data_source"] = snapshot["fetch_meta"]["data_source"]
        payload["stale"] = snapshot["fetch_meta"]["stale"]
        payload["fetch_warnings"] = snapshot["fetch_meta"]["fetch_warnings"]
    except BinanceAlphaError as exc:
        payload = {
            "intent": "get_risk_report",
            "symbol": args.symbol,
            "status": "error",
            "message": str(exc),
        }

    rendered = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if args.raw
        else json.dumps(payload, ensure_ascii=False, indent=2)
    )
    print(rendered)
    return 0 if payload.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
