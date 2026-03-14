"""Watchlist 持久化与对比快照构建。"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
WATCHLIST_COMPARE_STATE_PATH = ROOT / "data" / "watchlist_compare_state.json"


def load_watchlist() -> list[dict]:
    if not WATCHLIST_PATH.exists():
        return []
    return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))


def save_watchlist(items: list[dict]) -> None:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_compare_state() -> dict:
    if not WATCHLIST_COMPARE_STATE_PATH.exists():
        return {"mode": "momentum", "compare_at": None, "items": []}
    return json.loads(WATCHLIST_COMPARE_STATE_PATH.read_text(encoding="utf-8"))


def save_compare_state(state: dict) -> None:
    WATCHLIST_COMPARE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_COMPARE_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _fetch_watchlist_klines(candidates: list) -> dict[str, list[list[object]]]:
    from .binance_alpha import BinanceAlphaError, fetch_klines

    kline_map: dict[str, list[list[object]]] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_klines, candidate.market_symbol, "1m", 30): candidate.symbol
            for candidate in candidates
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                kline_map[symbol] = future.result()
            except BinanceAlphaError:
                kline_map[symbol] = []
    return kline_map


def _format_delta(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+d}"


def _status_change(prev: dict | None, current: dict) -> str:
    if prev is None:
        return "new"
    if current.get("status") == "missing":
        return "missing"

    prev_score = prev.get("opportunity_score")
    prev_risk = prev.get("risk_score")
    curr_score = current.get("opportunity_score")
    curr_risk = current.get("risk_score")
    score_delta = None if prev_score is None or curr_score is None else int(curr_score - prev_score)
    risk_delta = None if prev_risk is None or curr_risk is None else int(curr_risk - prev_risk)
    new_tags = set(current.get("tags") or []) - set(prev.get("tags") or [])
    removed_tags = set(prev.get("tags") or []) - set(current.get("tags") or [])

    if score_delta is not None and score_delta >= 8 and (risk_delta is None or risk_delta <= 0):
        return "improving"
    if (score_delta is not None and score_delta <= -8) or (risk_delta is not None and risk_delta >= 8):
        return "weakening"
    if new_tags or removed_tags:
        return "tags_changed"
    return "stable"


def _build_compare_summary(
    symbol: str,
    status_change: str,
    score_delta: int | None,
    risk_delta: int | None,
    new_tags: list[str],
    removed_tags: list[str],
) -> str:
    if status_change == "new":
        return f"{symbol} 首次纳入持续跟踪。"
    if status_change == "missing":
        return f"{symbol} 当前未出现在可用 Alpha 候选里，建议先确认是否下线或换池。"
    parts = [
        f"{symbol} 机会分 {_format_delta(score_delta)}",
        f"风险分 {_format_delta(risk_delta)}",
    ]
    if new_tags:
        parts.append(f"新增标签：{'、'.join(new_tags)}")
    if removed_tags:
        parts.append(f"移除标签：{'、'.join(removed_tags)}")
    label = {
        "improving": "状态转强",
        "weakening": "状态转弱",
        "tags_changed": "标签变化",
        "stable": "基本稳定",
    }.get(status_change, status_change)
    parts.append(label)
    return "，".join(parts) + "。"


def _compare_watchlist(current_items: list[dict], previous_items: list[dict]) -> dict:
    previous_map = {item.get("symbol"): item for item in previous_items}
    items: list[dict] = []
    status_counts = {
        "new": 0,
        "improving": 0,
        "weakening": 0,
        "tags_changed": 0,
        "stable": 0,
        "missing": 0,
    }

    for current in current_items:
        prev = previous_map.get(current.get("symbol"))
        current_tags = set(current.get("tags") or [])
        prev_tags = set((prev or {}).get("tags") or [])
        score_delta = None
        risk_delta = None
        if prev is not None and prev.get("opportunity_score") is not None and current.get("opportunity_score") is not None:
            score_delta = int(current["opportunity_score"] - prev["opportunity_score"])
        if prev is not None and prev.get("risk_score") is not None and current.get("risk_score") is not None:
            risk_delta = int(current["risk_score"] - prev["risk_score"])
        new_tags = sorted(current_tags - prev_tags)
        removed_tags = sorted(prev_tags - current_tags)
        change = _status_change(prev, current)
        status_counts[change] = status_counts.get(change, 0) + 1
        items.append(
            {
                "symbol": current.get("symbol"),
                "score": current.get("opportunity_score"),
                "risk": current.get("risk_score"),
                "score_delta": score_delta,
                "risk_delta": risk_delta,
                "new_tags": new_tags,
                "removed_tags": removed_tags,
                "status_change": change,
                "summary": _build_compare_summary(
                    current.get("symbol"),
                    change,
                    score_delta,
                    risk_delta,
                    new_tags,
                    removed_tags,
                ),
            }
        )

    improving = [item for item in items if item["status_change"] == "improving"]
    weakening = [item for item in items if item["status_change"] == "weakening"]
    turned_watch_only = [item["symbol"] for item in items if "watch_only" in item.get("new_tags", [])]
    quick_summary = (
        f"本轮共对比 {len(items)} 个 watchlist 标的，"
        f"转强 {len(improving)} 个，"
        f"转弱 {len(weakening)} 个，"
        f"新增跟踪 {status_counts.get('new', 0)} 个。"
    )
    return {
        "items": items,
        "status_counts": status_counts,
        "quick_summary": quick_summary,
        "highlights": {
            "top_improving": improving[0]["symbol"] if improving else None,
            "top_weakening": weakening[0]["symbol"] if weakening else None,
            "improving_symbols": [item["symbol"] for item in improving[:3]],
            "weakening_symbols": [item["symbol"] for item in weakening[:3]],
            "turned_watch_only": turned_watch_only[:3],
        },
    }


def _build_current_compare_items(watchlist_items: list[dict], mode: str) -> tuple[list[dict], dict]:
    from .binance_alpha import BinanceAlphaError, get_candidate_snapshot, list_alpha_candidates
    from .rules import build_discover_candidates, build_risk_report

    if not watchlist_items:
        return [], {"data_source": "live", "stale": False, "fetch_warnings": []}

    candidates, candidate_meta = list_alpha_candidates(limit=None, sort_by="volume", include_meta=True)
    tracked_symbols = {item.get("symbol") for item in watchlist_items if item.get("symbol")}
    tracked_candidates = [candidate for candidate in candidates if candidate.symbol in tracked_symbols]
    kline_map = _fetch_watchlist_klines(tracked_candidates)
    discover_items = build_discover_candidates(candidates, kline_map, mode)
    discover_map = {item["symbol"]: item for item in discover_items}

    compare_items: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    warnings = list(candidate_meta.get("fetch_warnings") or [])
    stale = bool(candidate_meta.get("stale"))
    for watch_item in watchlist_items:
        symbol = watch_item.get("symbol")
        discover_item = discover_map.get(symbol)
        if discover_item is None:
            compare_items.append(
                {
                    "symbol": symbol,
                    "note": watch_item.get("note", ""),
                    "opportunity_score": None,
                    "risk_score": None,
                    "tags": [],
                    "status": "missing",
                    "reason": "当前未在可用 Alpha 候选中找到该标的。",
                    "updated_at": now_iso,
                }
            )
            continue

        snapshot = get_candidate_snapshot(symbol)
        stale = stale or bool(snapshot["fetch_meta"]["stale"])
        warnings.extend(snapshot["fetch_meta"]["fetch_warnings"] or [])
        risk_report = build_risk_report(
            snapshot["candidate"],
            snapshot["meta"],
            snapshot["klines"],
            snapshot["book_ticker"],
        )
        compare_items.append(
            {
                "symbol": symbol,
                "note": watch_item.get("note", ""),
                "opportunity_score": discover_item["opportunity_score"],
                "risk_score": risk_report["risk_score"],
                "tags": discover_item["tags"],
                "reason": discover_item["reason"],
                "risk_summary": risk_report["risk_summary"],
                "risk_flags": risk_report["risk_flags"],
                "updated_at": now_iso,
            }
        )
    return compare_items, {
        "data_source": "cache_fallback" if stale else "live",
        "stale": stale,
        "fetch_warnings": list(dict.fromkeys(warnings)),
    }


def build_watchlist_compare_snapshot(
    mode: str = "momentum",
    persist: bool = False,
    require_previous_history: bool = False,
) -> dict | None:
    watchlist_items = load_watchlist()
    if not watchlist_items:
        return None

    previous_state = load_compare_state()
    previous_items = previous_state.get("items") or []
    current_items, fetch_meta = _build_current_compare_items(watchlist_items, mode)
    if require_previous_history and not previous_items:
        return None

    result = _compare_watchlist(current_items, previous_items)
    compare_at = datetime.now(timezone.utc).isoformat()
    next_state = {
        "mode": mode,
        "compare_at": compare_at,
        "items": current_items,
    }
    if persist:
        save_compare_state(next_state)

    payload = {
        "intent": "watchlist_compare",
        "mode": mode,
        "compare_at": compare_at,
        "count": len(current_items),
        "status_counts": result["status_counts"],
        "quick_summary": result["quick_summary"],
        "highlights": result["highlights"],
        "items": result["items"],
        "data_source": fetch_meta["data_source"],
        "stale": fetch_meta["stale"],
        "fetch_warnings": fetch_meta["fetch_warnings"],
    }
    return payload
