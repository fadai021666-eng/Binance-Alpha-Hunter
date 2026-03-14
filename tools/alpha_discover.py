#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = ROOT / "exports"
LATEST_SUBMISSION_DIRNAME = "latest_submission"
EXPORT_FORMATS = ("json", "txt", "both")
EXPORT_VERSION = "1.0"
PACKAGE_TYPE = "binance-alpha-hunter-submission-bundle"
PACKAGE_VERSION = "1.0"
DEGRADED_COMPONENT_LABELS = {
    "klines": "K 线数据",
    "token_meta": "代币元信息",
    "book_ticker": "盘口报价",
    "candidates": "候选列表",
    "unknown": "未知组件",
}
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.binance_alpha import BinanceAlphaError, fetch_klines, list_alpha_candidates  # noqa: E402
from lib.rules import (  # noqa: E402
    DURATION_CHOICES,
    DISCOVER_MODES,
    VOICE_STYLES,
    build_discover_candidates,
    build_narration_bundle,
    build_presentation_summary,
)
from tools.alpha_plan import _build_recent_trade_summary, _load_normalized_paper_trades  # noqa: E402
from tools.alpha_watchlist import build_watchlist_compare_snapshot  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="发现 Binance Alpha 候选标的")
    parser.add_argument("--limit", type=int, default=10, help="返回数量")
    parser.add_argument(
        "--sort",
        choices=["score", "volume", "change", "liquidity", "new"],
        default="volume",
        help="排序方式",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(DISCOVER_MODES),
        default="momentum",
        help="筛选模式",
    )
    parser.add_argument("--keyword", default="", help="按 symbol/name/tag 过滤")
    parser.add_argument("--min-volume", type=float, default=0.0, help="最小 24h 成交额")
    parser.add_argument("--min-liquidity", type=float, default=0.0, help="最小流动性")
    parser.add_argument("--competition-mode", action="store_true", help="一键比赛模式：自动启用展示、旁白、比赛风格和导出")
    parser.add_argument("--presentation", action="store_true", help="输出适合演示和录屏的榜单摘要")
    parser.add_argument("--narration", action="store_true", help="在展示模式基础上生成中文旁白稿")
    parser.add_argument(
        "--voice-style",
        choices=sorted(VOICE_STYLES),
        default="neutral",
        help="旁白风格：neutral / energetic / competition",
    )
    parser.add_argument(
        "--duration",
        type=int,
        choices=sorted(DURATION_CHOICES),
        default=30,
        help="口播时长：15 / 30 / 60 秒",
    )
    parser.add_argument("--export", action="store_true", help="将当前结果导出为投稿/演示素材文件")
    parser.add_argument(
        "--export-dir",
        default=str(DEFAULT_EXPORT_DIR),
        help="导出目录，默认写到 skill 目录下 exports/",
    )
    parser.add_argument(
        "--export-format",
        choices=EXPORT_FORMATS,
        default="json",
        help="导出格式：json / txt / both",
    )
    parser.add_argument("--raw", action="store_true", help="输出紧凑 JSON")
    return parser


def _apply_competition_mode(args) -> None:
    if not args.competition_mode:
        return
    args.presentation = True
    args.narration = True
    args.voice_style = "competition"
    args.duration = 60
    args.export = True
    args.export_format = "both"
    args.sort = "score"


def _fetch_candidate_klines(items) -> tuple[dict[str, list[list[object]]], dict[str, object]]:
    kline_map: dict[str, list[list[object]]] = {}
    warnings: list[str] = []
    stale = False
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_klines, item.market_symbol, "1m", 30, True): item.symbol
            for item in items
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result, meta = future.result()
                kline_map[symbol] = result
                stale = stale or bool(meta.get("stale"))
                warnings.extend(meta.get("fetch_warnings") or [])
            except BinanceAlphaError as exc:
                kline_map[symbol] = []
                warnings.append(f"{symbol} 的 kline 拉取失败，已降级为空：{exc}")
                stale = True
    dedup_warnings = list(dict.fromkeys(warnings))
    return kline_map, {
        "data_source": "cache_fallback" if stale else "live",
        "stale": stale,
        "fetch_warnings": dedup_warnings,
    }


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_export_meta(payload: dict[str, Any], args, exported_at: str) -> dict[str, Any]:
    ready_for_submission = bool(
        payload.get("presentation")
        and payload.get("narration")
        and payload.get("short_caption")
        and payload.get("demo_script")
    )
    return {
        "exported_at": exported_at,
        "mode": payload.get("mode", args.mode),
        "voice_style": payload.get("voice_style", args.voice_style),
        "duration": payload.get("target_duration_sec", args.duration),
        "source": payload.get("source"),
        "export_version": EXPORT_VERSION,
        "ready_for_submission": ready_for_submission,
    }


def _build_data_freshness(payload: dict[str, Any]) -> str:
    if payload.get("stale"):
        return "当前结果包含缓存回退，适合展示连续性，不应默认视为全量实时数据。"
    return "当前结果来自实时链路，数据新鲜度正常。"


def _build_data_status(payload: dict[str, Any]) -> dict[str, Any]:
    warnings = list(payload.get("fetch_warnings") or [])
    degraded_components: list[str] = []
    for warning in warnings:
        lowered = warning.lower()
        if "kline" in lowered or "klines" in lowered:
            degraded_components.append("klines")
        elif "token meta" in lowered or "meta" in lowered:
            degraded_components.append("token_meta")
        elif "book ticker" in lowered or "book_ticker" in lowered:
            degraded_components.append("book_ticker")
        elif "候选" in warning or "token list" in lowered or "exchange" in lowered:
            degraded_components.append("candidates")
        else:
            degraded_components.append("unknown")
    degraded_components = list(dict.fromkeys(degraded_components))
    degraded_components_zh = [DEGRADED_COMPONENT_LABELS.get(item, item) for item in degraded_components]
    return {
        "data_source": payload.get("data_source", "live"),
        "stale": bool(payload.get("stale")),
        "warning_count": len(warnings),
        "has_fetch_warnings": bool(warnings),
        "degraded_components": degraded_components,
        "degraded_components_zh": degraded_components_zh,
    }


def _build_export_bundle(payload: dict[str, Any], args, exported_at: str) -> dict[str, Any]:
    data_status = _build_data_status(payload)
    recent_trade_summary = _build_recent_trade_summary(_load_normalized_paper_trades())
    try:
        watchlist_compare_summary = build_watchlist_compare_snapshot(
            mode=payload.get("mode", args.mode),
            persist=False,
            require_previous_history=True,
        )
    except Exception:
        watchlist_compare_summary = None
    return {
        "meta": _build_export_meta(payload, args, exported_at),
        "items": payload.get("items", []),
        "data_source": payload.get("data_source", "live"),
        "stale": bool(payload.get("stale")),
        "fetch_warnings": list(payload.get("fetch_warnings") or []),
        "data_freshness": _build_data_freshness(payload),
        "data_status": data_status,
        "degraded_components": data_status.get("degraded_components", []),
        "degraded_components_zh": data_status.get("degraded_components_zh", []),
        "presentation": payload.get("presentation"),
        "narration": payload.get("narration"),
        "short_caption": payload.get("short_caption"),
        "demo_script": payload.get("demo_script"),
        "recent_trade_summary": recent_trade_summary,
        "watchlist_compare_summary": watchlist_compare_summary,
    }


def _build_export_basename(payload: dict[str, Any], args, timestamp_slug: str) -> str:
    mode = payload.get("mode", args.mode)
    voice_style = payload.get("voice_style", args.voice_style)
    duration = payload.get("target_duration_sec", args.duration)
    return f"alpha-hunter_{mode}_{voice_style}_{duration}s_{timestamp_slug}"


def _build_txt_export(bundle: dict[str, Any]) -> str:
    presentation = bundle.get("presentation") or {}
    narration = bundle.get("narration") or {}
    meta = bundle.get("meta") or {}
    lines = [
        f"标题：{presentation.get('title') or 'Binance Alpha Hunter 导出稿'}",
        f"导出时间：{meta.get('exported_at')}",
        f"模式：{meta.get('mode')}",
        f"旁白风格：{meta.get('voice_style')}",
        f"时长：{meta.get('duration')} 秒",
        "",
        f"短文案：{bundle.get('short_caption') or '未生成 short_caption'}",
        "",
        f"开场：{narration.get('opening') or '未生成 opening'}",
        "",
        f"正文：{narration.get('script') or '未生成 script'}",
        "",
        f"结尾：{narration.get('closing') or '未生成 closing'}",
    ]
    return "\n".join(lines).strip() + "\n"


def _build_manifest(bundle: dict[str, Any], bundle_name: str, latest_copy: bool) -> dict[str, Any]:
    meta = bundle.get("meta") or {}
    presentation = bundle.get("presentation") or {}
    recent_trade_summary = bundle.get("recent_trade_summary") or {}
    watchlist_compare_summary = bundle.get("watchlist_compare_summary") or {}
    data_status = _build_data_status(bundle)
    top_picks = list(presentation.get("top_picks") or [])
    watch_only = list(presentation.get("watch_only") or [])
    return {
        "package_type": PACKAGE_TYPE,
        "package_version": PACKAGE_VERSION,
        "bundle_name": bundle_name,
        "generated_at": meta.get("exported_at"),
        "mode": meta.get("mode"),
        "voice_style": meta.get("voice_style"),
        "duration": meta.get("duration"),
        "ready_for_submission": meta.get("ready_for_submission"),
        "latest_copy": latest_copy,
        "files": {
            "submission_json": "submission.json",
            "voiceover_txt": "voiceover.txt",
            "cover_md": "cover.md",
        },
        "entrypoints": {
            "caption": "submission.json#short_caption",
            "narration": "submission.json#narration",
            "presentation": "submission.json#presentation",
        },
        "scoreboard": {
            "market_view": presentation.get("market_view"),
            "top_picks": [
                {
                    "rank": item.get("rank"),
                    "symbol": item.get("symbol"),
                    "score": item.get("score"),
                    "verdict": item.get("verdict"),
                    "summary": item.get("summary"),
                }
                for item in top_picks
            ],
            "watch_only": [
                {
                    "symbol": item.get("symbol"),
                    "reason": item.get("reason") or item.get("summary"),
                }
                for item in watch_only
            ],
            "risk_notice": presentation.get("risk_notice"),
            "counts": {
                "top_picks": len(top_picks),
                "watch_only": len(watch_only),
            },
        },
        "trade_snapshot": (
            {
                "symbol": recent_trade_summary.get("symbol"),
                "style": recent_trade_summary.get("style"),
                "action": recent_trade_summary.get("action"),
                "created_at": recent_trade_summary.get("created_at"),
                "confidence": recent_trade_summary.get("confidence"),
                "execution_summary": recent_trade_summary.get("execution_summary"),
            }
            if recent_trade_summary
            else None
        ),
        "trade_history_count": len(_load_normalized_paper_trades()),
        "tracking_snapshot": (
            {
                "quick_summary": watchlist_compare_summary.get("quick_summary"),
                "status_counts": watchlist_compare_summary.get("status_counts"),
                "highlights": watchlist_compare_summary.get("highlights"),
            }
            if watchlist_compare_summary
            else None
        ),
        "data_status": data_status,
    }


def _write_manifest(target_dir: Path, bundle: dict[str, Any], bundle_name: str, latest_copy: bool) -> Path:
    manifest_path = target_dir / "manifest.json"
    manifest = _build_manifest(bundle, bundle_name=bundle_name, latest_copy=latest_copy)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _build_cover_md(bundle: dict[str, Any], package_dir_name: str) -> str:
    meta = bundle.get("meta") or {}
    presentation = bundle.get("presentation") or {}
    recent_trade_summary = bundle.get("recent_trade_summary") or {}
    watchlist_compare_summary = bundle.get("watchlist_compare_summary") or {}
    data_status = _build_data_status(bundle)
    top_picks = list((presentation.get("top_picks") or []))
    watch_only = list((presentation.get("watch_only") or []))

    title = presentation.get("title") or "Binance Alpha Hunter 投稿目录包"
    exported_at = meta.get("exported_at", "")
    mode = meta.get("mode", "")
    voice_style = meta.get("voice_style", "")
    duration = meta.get("duration", "")
    work_summary = (
        f"这是一份基于 Binance Alpha Hunter 的 {mode} 模式导出包，"
        f"已同时整理榜单、旁白稿和演示分段，适合录屏、截图和投稿。"
    )
    market_view = presentation.get("market_view") or "暂无市场判断摘要。"
    risk_notice = presentation.get("risk_notice") or "暂无风险提示。"
    short_caption = bundle.get("short_caption") or "暂无 short_caption。"

    top_pick_lines = []
    for item in top_picks:
        top_pick_lines.append(
            f"- #{item.get('rank')} {item.get('symbol')} | 分数 {item.get('score')} | {item.get('verdict')} | {item.get('summary')}"
        )
    if not top_pick_lines:
        top_pick_lines.append("- 暂无 top picks。")

    watch_only_lines = []
    for item in watch_only:
        watch_only_lines.append(
            f"- {item.get('symbol')} | 分数 {item.get('score')} | {item.get('summary') or item.get('reason')}"
        )
    if not watch_only_lines:
        watch_only_lines.append("- 当前没有明显的 watch only 名单。")

    file_notes = [
        "- `submission.json`：完整结构化结果，包含榜单、展示、旁白和分段脚本。",
        "- `voiceover.txt`：可直接拿来录屏念稿的文本版。",
        "- `cover.md`：当前目录包说明页，适合快速预览和转发。",
        "- `manifest.json`：供后续自动化脚本读取目录包元信息和入口。",
    ]

    recent_trade_lines = []
    if recent_trade_summary:
        recent_trade_lines = [
            f"- symbol：`{recent_trade_summary.get('symbol')}`",
            f"- style：`{recent_trade_summary.get('style')}`",
            f"- action：`{recent_trade_summary.get('action')}`",
            f"- created_at：`{recent_trade_summary.get('created_at')}`",
            f"- confidence：`{recent_trade_summary.get('confidence')}`",
            f"- plan_reason：{recent_trade_summary.get('plan_reason') or '暂无'}",
            f"- execution_summary：{recent_trade_summary.get('execution_summary') or '暂无'}",
            f"- 风险结论摘要：{recent_trade_summary.get('risk_summary') or '暂无'}",
        ]
    else:
        recent_trade_lines = [
            "暂无 paper trade 历史。",
        ]

    tracking_lines = []
    if watchlist_compare_summary:
        highlights = watchlist_compare_summary.get("highlights") or {}
        tracking_lines = [
            watchlist_compare_summary.get("quick_summary") or "暂无 watchlist 对比摘要。",
            f"- 转强标的：{'、'.join(highlights.get('improving_symbols') or []) or '暂无'}",
            f"- 转弱标的：{'、'.join(highlights.get('weakening_symbols') or []) or '暂无'}",
            f"- 转为 watch_only：{'、'.join(highlights.get('turned_watch_only') or []) or '暂无'}",
        ]
    else:
        tracking_lines = [
            "暂无 watchlist 对比历史。",
        ]

    data_status_lines = [
        f"- 数据来源：`{data_status.get('data_source')}`",
        f"- 是否陈旧：`{str(data_status.get('stale')).lower()}`",
        f"- 抓取告警数量：`{data_status.get('warning_count')}`",
    ]
    warnings = list(bundle.get("fetch_warnings") or [])
    if warnings:
        data_status_lines.append(f"- 数据状态摘要：{bundle.get('data_freshness')}")
        if data_status.get("degraded_components_zh"):
            data_status_lines.append(f"- 降级组件：{'、'.join(data_status.get('degraded_components_zh') or [])}")
        data_status_lines.extend([f"- 告警：{warning}" for warning in warnings[:3]])
    else:
        data_status_lines.append("- 当前数据链路正常。")
        data_status_lines.append("- 当前没有降级组件。")

    lines = [
        f"# {title}",
        "",
        f"- 导出时间：`{exported_at}`",
        f"- mode：`{mode}`",
        f"- voice_style：`{voice_style}`",
        f"- duration：`{duration}s`",
        f"- 导出目录：`{package_dir_name}`",
        "",
        "## 一句话作品说明",
        "",
        work_summary,
        "",
        "## 本次市场判断摘要",
        "",
        market_view,
        "",
        "## 数据状态",
        "",
        *data_status_lines,
        "",
        "## Top Picks 摘要",
        "",
        *top_pick_lines,
        "",
        "## Watch Only 摘要",
        "",
        *watch_only_lines,
        "",
        "## 风险提示",
        "",
        risk_notice,
        "",
        "## Short Caption",
        "",
        short_caption,
        "",
        "## 最近执行摘要",
        "",
        *recent_trade_lines,
        "",
        "## 最近观察变化",
        "",
        *tracking_lines,
        "",
        "## 文件说明",
        "",
        *file_notes,
        "",
    ]
    return "\n".join(lines)


def _refresh_latest_submission(
    export_dir: Path,
    submission_path: Path,
    voiceover_path: Path,
    cover_path: Path,
    bundle: dict[str, Any],
) -> Path:
    latest_dir = export_dir / LATEST_SUBMISSION_DIRNAME
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(submission_path, latest_dir / "submission.json")
    shutil.copy2(voiceover_path, latest_dir / "voiceover.txt")
    shutil.copy2(cover_path, latest_dir / "cover.md")
    _write_manifest(latest_dir, bundle, bundle_name=LATEST_SUBMISSION_DIRNAME, latest_copy=True)
    return latest_dir


def _export_payload(payload: dict[str, Any], args) -> tuple[str, str, list[str]]:
    export_dir = Path(args.export_dir).expanduser()
    export_dir.mkdir(parents=True, exist_ok=True)

    exported_at = datetime.now(timezone.utc).isoformat()
    timestamp_slug = _timestamp_slug()
    basename = _build_export_basename(payload, args, timestamp_slug)
    bundle = _build_export_bundle(payload, args, exported_at)
    package_dir = export_dir / basename
    package_dir.mkdir(parents=True, exist_ok=False)

    exported_files: list[str] = []
    json_path = package_dir / "submission.json"
    json_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    exported_files.append(str(json_path))

    txt_path = package_dir / "voiceover.txt"
    txt_path.write_text(_build_txt_export(bundle), encoding="utf-8")
    exported_files.append(str(txt_path))

    cover_path = package_dir / "cover.md"
    cover_path.write_text(_build_cover_md(bundle, package_dir.name) + "\n", encoding="utf-8")
    exported_files.append(str(cover_path))
    _write_manifest(package_dir, bundle, bundle_name=package_dir.name, latest_copy=False)

    latest_submission_dir = _refresh_latest_submission(
        export_dir,
        json_path,
        txt_path,
        cover_path,
        bundle,
    )

    latest_path = export_dir / "LATEST.txt"
    latest_path.write_text(str(package_dir) + "\n", encoding="utf-8")
    exported_files.append(str(latest_path))

    return str(package_dir), str(latest_submission_dir), exported_files


def main() -> int:
    args = build_parser().parse_args()
    _apply_competition_mode(args)

    items, candidate_meta = list_alpha_candidates(
        limit=None,
        sort_by=args.sort if args.sort != "score" else "volume",
        include_meta=True,
    )
    kline_map, kline_meta = _fetch_candidate_klines(items)
    enhanced_items = build_discover_candidates(items, kline_map, args.mode)
    mode_filtered = [item for item in enhanced_items if item.get("mode_match")]
    if mode_filtered:
        enhanced_items = mode_filtered

    keyword = args.keyword.strip().lower()
    if keyword:
        enhanced_items = [
            item
            for item in enhanced_items
            if keyword in item["symbol"].lower()
            or keyword in item["reason"].lower()
            or any(keyword in tag.lower() for tag in item["tags"])
            or any(keyword in text.lower() for text in item["explain"])
        ]

    enhanced_items = [
        item
        for item in enhanced_items
        if item["volume_24h"] >= args.min_volume and item["liquidity"] >= args.min_liquidity
    ]

    if args.sort == "score":
        enhanced_items.sort(key=lambda item: item["opportunity_score"], reverse=True)
    elif args.sort == "change":
        enhanced_items.sort(key=lambda item: abs(item["24h_change"]), reverse=True)
    elif args.sort == "liquidity":
        enhanced_items.sort(key=lambda item: item["liquidity"], reverse=True)
    elif args.sort == "new":
        enhanced_items.sort(key=lambda item: ("new" in item["tags"], item["opportunity_score"]), reverse=True)
    else:
        enhanced_items.sort(key=lambda item: item["volume_24h"], reverse=True)

    limited = enhanced_items[: max(args.limit, 0)] if args.limit > 0 else enhanced_items
    for item in limited:
        item.pop("mode_match", None)
    payload = {
        "intent": "discover_alpha",
        "competition_mode": bool(args.competition_mode),
        "sort": args.sort,
        "mode": args.mode,
        "keyword": args.keyword,
        "count": len(limited),
        "items": limited,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "binance-alpha-public",
        "data_source": "cache_fallback"
        if candidate_meta.get("stale") or kline_meta.get("stale")
        else "live",
        "stale": bool(candidate_meta.get("stale") or kline_meta.get("stale")),
        "fetch_warnings": list(
            dict.fromkeys(
                list(candidate_meta.get("fetch_warnings") or [])
                + list(kline_meta.get("fetch_warnings") or [])
            )
        ),
    }
    if args.competition_mode:
        payload["competition_profile"] = {
            "presentation": True,
            "narration": True,
            "voice_style": "competition",
            "duration": 60,
            "export": True,
            "export_format": "both",
            "sort": "score",
        }
    if args.presentation:
        presentation = build_presentation_summary(limited, args.mode)
        payload["presentation"] = presentation
        if args.narration:
            data_status = _build_data_status(payload)
            payload.update(
                build_narration_bundle(
                    presentation,
                    voice_style=args.voice_style,
                    duration=args.duration,
                    data_status=data_status,
                )
            )
    if args.export:
        exported_dir, latest_submission_dir, exported_files = _export_payload(payload, args)
        payload["exported_dir"] = exported_dir
        payload["latest_submission_dir"] = latest_submission_dir
        payload["exported_files"] = exported_files

    rendered = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if args.raw
        else json.dumps(payload, ensure_ascii=False, indent=2)
    )
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
