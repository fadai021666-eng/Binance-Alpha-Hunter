from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from .types import AlphaCandidate


STYLE_PRESETS: dict[str, dict[str, float]] = {
    "conservative": {
        "entry_pullback": 0.015,
        "min_stop": 0.035,
        "rr1": 1.8,
        "rr2": 3.0,
        "position_pct": 0.012,
    },
    "balanced": {
        "entry_pullback": 0.008,
        "min_stop": 0.05,
        "rr1": 2.0,
        "rr2": 3.5,
        "position_pct": 0.02,
    },
    "aggressive": {
        "entry_pullback": 0.0,
        "min_stop": 0.075,
        "rr1": 2.2,
        "rr2": 4.2,
        "position_pct": 0.03,
    },
}

DISCOVER_MODES = {"momentum", "safe", "early", "contrarian"}
VOICE_STYLES = {"neutral", "energetic", "competition"}
DURATION_CHOICES = {15, 30, 60}


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
        synchronized_expansion = bool(metrics["volume_spike"] and (candidate.change_24h >= 8 or float(metrics["return_15m"]) >= 0.02))
        illiquid = bool(candidate.liquidity < 500_000 or liquidity_percentile <= 0.22 or candidate.volume_24h < 800_000)
        overheated = bool(candidate.change_24h >= 35 or (float(metrics["return_5m"]) >= 0.04 and metrics["volume_spike"]))
        watch_only = bool(illiquid or overheated or (is_new and liquidity_percentile < 0.35))

        score = 35
        if 4 <= candidate.change_24h <= 18:
            score += 12
        elif 18 < candidate.change_24h <= 35:
            score += 16
        elif 0 < candidate.change_24h < 4:
            score += 5
        elif -12 <= candidate.change_24h < 0:
            score -= 4
        elif candidate.change_24h < -12:
            score -= 12

        score += int(volume_percentile * 18)
        if synchronized_expansion:
            score += 12
        if is_new:
            score += 8
        if metrics["price_breakout"]:
            score += 8
        if illiquid:
            score -= 15
        if overheated:
            score -= 12
        if float(metrics["return_5m"]) < -0.03:
            score -= 6
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


def _presentation_verdict(item: dict[str, Any]) -> str:
    tags = set(item.get("tags") or [])
    score = int(item.get("opportunity_score") or 0)
    if "watch_only" in tags:
        return "只适合观察"
    if score >= 78:
        return "优先关注"
    if score >= 62:
        return "可以跟踪"
    return "观察为主"


def _strip_terminal_punctuation(text: str) -> str:
    return text.strip().rstrip("。；，,; ")


def _build_summary_text(explain: list[str], fallback: str) -> str:
    parts = [_strip_terminal_punctuation(item) for item in explain if item]
    parts = [item for item in parts if item][:2]
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0] + "。"
    return f"{parts[0]}，且{parts[1]}。"


def _build_market_view(items: list[dict[str, Any]], mode: str) -> str:
    if not items:
        return f"当前 {mode} 模式下没有足够强的 Alpha 候选，市场更适合等待。"

    avg_score = statistics.fmean(float(item.get("opportunity_score") or 0) for item in items)
    hot_count = sum(1 for item in items if "hot" in (item.get("tags") or []))
    overheated_count = sum(1 for item in items if "overheated" in (item.get("tags") or []))
    watch_only_count = sum(1 for item in items if "watch_only" in (item.get("tags") or []))

    if mode == "momentum":
        tone = "当前 Alpha 市场偏动量，强势标的主要集中在放量和高热度方向。"
    elif mode == "safe":
        tone = "当前 Alpha 市场里仍能找到相对稳一点的候选，但更适合精选而不是撒网。"
    elif mode == "early":
        tone = "当前 Alpha 市场更像早期轮动阶段，适合盯新标的和刚放量的名字。"
    else:
        tone = "当前 Alpha 市场有少量回撤后仍保留成交的名字，适合反向观察。"

    heat = []
    if avg_score >= 72:
        heat.append("整体机会分偏高")
    elif avg_score >= 58:
        heat.append("整体机会分中等")
    else:
        heat.append("整体机会分偏谨慎")

    if hot_count:
        heat.append(f"其中 {hot_count} 个带明显热度标签")
    if overheated_count:
        heat.append(f"{overheated_count} 个已经偏热")
    if watch_only_count:
        heat.append(f"{watch_only_count} 个更适合先观察")

    return f"{tone}{'，'.join(heat)}。"


def build_presentation_summary(items: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    ranked_items = sorted(items, key=lambda item: int(item.get("opportunity_score") or 0), reverse=True)
    top_candidates = [item for item in ranked_items if "watch_only" not in (item.get("tags") or [])]
    if not top_candidates:
        top_candidates = ranked_items

    top_picks = []
    for index, item in enumerate(top_candidates[:3], start=1):
        explain = list(item.get("explain") or [])
        summary = _build_summary_text(explain, item.get("reason", ""))
        top_picks.append(
            {
                "rank": index,
                "symbol": item["symbol"],
                "score": item["opportunity_score"],
                "verdict": _presentation_verdict(item),
                "summary": summary or item.get("reason", ""),
            }
        )

    watch_only_items = [
        {
            "symbol": item["symbol"],
            "score": item["opportunity_score"],
            "reason": item["reason"],
            "summary": _build_summary_text(list(item.get("explain") or []), item["reason"]),
        }
        for item in ranked_items
        if "watch_only" in (item.get("tags") or [])
    ][:3]

    if watch_only_items:
        watch_symbols = "、".join(item["symbol"] for item in watch_only_items)
        risk_notice = (
            f"{watch_symbols} 当前更适合观察，不适合直接执行；主要原因通常是过热、低流动性或新标的承接还没确认。"
        )
    else:
        risk_notice = "当前展示标的里没有明显的只看不动名单，但仍应先计划、后确认、再考虑执行。"

    return {
        "title": f"Binance Alpha Hunter 榜单展示：{mode} 模式",
        "mode": mode,
        "market_view": _build_market_view(ranked_items, mode),
        "top_picks": top_picks,
        "watch_only": watch_only_items,
        "risk_notice": risk_notice,
    }


def _estimate_spoken_words(text: str) -> int:
    filtered = [
        ch for ch in text
        if ch.strip() and ch not in "，。！？；：、“”‘’（）()【】[]《》…,.!?;:-"
    ]
    return max(1, round(len(filtered) * 0.7))


def _compression_level(duration: int) -> str:
    if duration <= 15:
        return "high"
    if duration <= 30:
        return "medium"
    return "low"


def build_narration_bundle(
    presentation: dict[str, Any],
    voice_style: str = "neutral",
    duration: int = 30,
    data_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if voice_style not in VOICE_STYLES:
        raise ValueError(f"unsupported voice style: {voice_style}")
    if duration not in DURATION_CHOICES:
        raise ValueError(f"unsupported duration: {duration}")

    top_picks = list(presentation.get("top_picks") or [])
    watch_only = list(presentation.get("watch_only") or [])
    mode = presentation.get("mode", "momentum")
    market_view = presentation.get("market_view", "")
    risk_notice = presentation.get("risk_notice", "")

    if top_picks:
        top_pick_line = "今天优先讲的标的是" + "、".join(
            f"{item['symbol']}（{item['verdict']}）" for item in top_picks[:3]
        ) + "。"
    else:
        top_pick_line = "今天没有特别强的优先标的，更适合轻仓观察。"

    top_pick_reason_line_1 = ""
    top_pick_reason_line_2 = ""
    if top_picks:
        if top_picks[0].get("summary"):
            top_pick_reason_line_1 = f"{top_picks[0]['symbol']} 这次入选，核心原因是{top_picks[0]['summary']}"
        if len(top_picks) > 1 and top_picks[1].get("summary"):
            top_pick_reason_line_2 = f"{top_picks[1]['symbol']} 这次入选，核心原因是{top_picks[1]['summary']}"

    if watch_only:
        watch_line = "只适合观察的名字有" + "、".join(item["symbol"] for item in watch_only[:3]) + "。"
    else:
        watch_line = "这次榜单里暂时没有特别明显的只看不动名单。"

    top_symbols = "、".join(item["symbol"] for item in top_picks[:3]) or "当前以观察为主"
    primary_pick = top_picks[0]["symbol"] if top_picks else "当前以观察为主"
    short_market_view = market_view.split("。", 1)[0] + "。" if "。" in market_view else market_view
    short_risk_notice = risk_notice.split("；", 1)[0] + "。" if "；" in risk_notice else risk_notice
    data_status = data_status or {}
    degraded_components_zh = list(data_status.get("degraded_components_zh") or [])
    if degraded_components_zh:
        data_status_line = f"当前数据链路有降级回退，主要涉及：{'、'.join(degraded_components_zh)}。"
    else:
        data_status_line = "当前数据链路整体正常。"

    if duration == 15:
        content_open = short_market_view
        content_body = "今天先看" + primary_pick + "，它是这一轮最值得先讲的标的。"
        if top_pick_reason_line_1:
            content_body += top_pick_reason_line_1
        content_watch = ""
        content_risk = short_risk_notice + data_status_line
        duration_sec = 15
        demo_script = [
            {"segment": "开场", "seconds": "0-2", "prompt": ""},
            {"segment": "开场和判断", "seconds": "0-5", "prompt": market_view},
            {"segment": "重点标的", "seconds": "5-10", "prompt": content_body},
            {"segment": "风险提示", "seconds": "10-15", "prompt": risk_notice},
        ]
        preserve_demo_prompts = False
    elif duration == 60:
        content_open = market_view
        content_body = top_pick_line
        if top_pick_reason_line_1:
            content_body += top_pick_reason_line_1
        if top_pick_reason_line_2:
            content_body += " " + top_pick_reason_line_2
        content_watch = watch_line
        content_risk = risk_notice + data_status_line + "这份结果不是只给数据，也是在强调执行前的筛选和风控。"
        duration_sec = 60
        demo_script = [
            {"segment": "开场", "seconds": "0-8", "prompt": ""},
            {"segment": "市场判断", "seconds": "8-20", "prompt": content_open},
            {"segment": "重点标的", "seconds": "20-42", "prompt": content_body},
            {"segment": "观察名单", "seconds": "42-52", "prompt": content_watch},
            {"segment": "风险提示与结尾", "seconds": "52-60", "prompt": content_risk},
        ]
        preserve_demo_prompts = False
    else:
        content_open = market_view
        content_body = "今天优先讲的标的是" + "、".join(
            f"{item['symbol']}（{item['verdict']}）" for item in top_picks[:2]
        ) + "。" if top_picks else top_pick_line
        if top_pick_reason_line_1:
            content_body += top_pick_reason_line_1
        content_watch = watch_line
        content_risk = risk_notice + data_status_line
        duration_sec = 30
        demo_script = [
            {"segment": "开场", "seconds": "0-5", "prompt": ""},
            {"segment": "市场判断", "seconds": "5-12", "prompt": content_open},
            {"segment": "重点标的", "seconds": "12-22", "prompt": content_body},
            {"segment": "观察名单", "seconds": "22-27", "prompt": content_watch},
            {"segment": "风险提示", "seconds": "27-30", "prompt": content_risk},
        ]
        preserve_demo_prompts = False

    if voice_style == "energetic":
        opening = f"下面这版是 Binance Alpha Hunter 的 {mode} 高节奏展示，我们直接看机会点。"
        script = (
            f"{content_open}"
            f"{content_body}"
            f"{content_watch}"
            f"{content_risk}"
            + ("记住，这里讲的是高质量候选，不是让你无计划冲进去。" if duration >= 30 else "")
        ).strip()
        closing = (
            "如果你要继续录屏，下一步就直接切到风险摘要和交易计划。"
            if duration >= 30
            else "下一步直接切风险摘要。"
        )
        short_caption = (
            f"Alpha Hunter {mode} 快速榜单：{top_symbols}。"
            + (
                "适合 15 秒快讲。"
                if duration == 15
                else "有机会，但先看风控，再谈执行。"
            )
            + (" 当前有缓存回退。" if degraded_components_zh else " 数据正常。")
        )
        tone_notes = "节奏更快，更有推进感，适合短视频、宣传片段、录屏亮点展示。"
        use_case = "适合短视频、宣传展示、节奏更快的录屏解说。"
    elif voice_style == "competition":
        opening = f"这是 Binance Alpha Hunter 的 {mode} 比赛展示，重点看机会发现和风控闭环。"
        if duration == 60:
            competition_picks = "、".join(
                f"{item['symbol']}（{item['verdict']}）" for item in top_picks[:2]
            ) or top_symbols
            competition_pick_reason = ""
            if top_picks:
                competition_pick_reason = f"{top_picks[0]['symbol']} 的理由是{top_picks[0].get('summary') or ''}"
            if len(top_picks) > 1:
                competition_pick_reason += f"{top_picks[1]['symbol']} 则是{top_picks[1].get('summary') or ''}"
            competition_risk_line = (
                "没有明显只看不动名单，但执行前仍要先看风险。"
                if not watch_only
                else watch_line + short_risk_notice
            )
            competition_data_line = (
                f"当前有降级回退，主要涉及：{'、'.join(degraded_components_zh)}。"
                if degraded_components_zh
                else "当前数据链路正常。"
            )
            script = (
                f"{content_open}"
                f"这轮优先看 {competition_picks}。"
                f"{competition_pick_reason}"
                f"{competition_risk_line}"
                f"{competition_data_line}"
                "这份结果已经把发现、筛选和执行前风控串成闭环。"
            ).strip()
        else:
            script = (
                f"{content_open}"
                f"{content_body}"
                f"{content_watch}"
                f"{content_risk}"
                + (
                    "这份结果不是只给数据，而是把候选发现、筛选解释和执行前风控串成了一条完整链路。"
                    if duration >= 30
                    else ""
                )
            ).strip()
        closing = (
            "如果继续展开，我会先验证风险摘要，再基于风格生成交易计划，形成完整闭环。"
            if duration >= 30
            else "下一步我会把风险和计划闭环补齐。"
        )
        if duration == 60:
            demo_script = [
                {"segment": "开场", "seconds": "0-8", "prompt": opening},
                {"segment": "市场判断", "seconds": "8-18", "prompt": content_open},
                {"segment": "重点标的", "seconds": "18-36", "prompt": f"这轮优先看 {competition_picks}。{competition_pick_reason}"},
                {"segment": "观察名单", "seconds": "36-46", "prompt": competition_risk_line},
                {"segment": "风险提示与结尾", "seconds": "46-60", "prompt": f"{competition_data_line}{closing}"},
            ]
            preserve_demo_prompts = True
        short_caption = (
            f"Binance Alpha Hunter 作品展示：{mode} 模式下重点关注 {top_symbols}。"
            "不仅发现机会，也把风险和执行边界说明白。"
            + (" 当前含降级回退。" if degraded_components_zh else " 当前数据链路正常。")
        )
        tone_notes = "更强调方法价值、机会发现、风险控制和产出闭环，适合比赛投稿。"
        use_case = "适合作品投稿、比赛答辩、强调方法论和闭环能力的演示。"
    else:
        opening = f"这是一版 Binance Alpha Hunter 的 {mode} 模式展示。"
        script = (
            f"{content_open}"
            f"{content_body}"
            f"{content_watch}"
            f"{content_risk}"
            + ("这份榜单更适合用来做筛选和讲解，不代表可以直接无脑执行。" if duration >= 30 else "")
        ).strip()
        closing = (
            "如果要继续往下做，我建议先看风险摘要，再决定是否生成交易计划。"
            if duration >= 30
            else "下一步建议先看风险摘要。"
        )
        short_caption = (
            f"Binance Alpha Hunter {mode} 模式榜单：{top_symbols}。"
            + ("适合快速录屏讲解。" if duration == 15 else "先看榜单，再看风险，不追无计划的单。")
            + (" 当前有降级回退。" if degraded_components_zh else " 当前数据链路整体正常。")
        )
        tone_notes = "客观、平稳、信息密度适中，适合常规产品演示和讲解。"
        use_case = "适合常规产品演示、日常录屏讲解、稳态说明。"

    script = script.replace("。。", "。").replace("..", ".").strip()
    estimated_words = _estimate_spoken_words(opening + script + closing)

    if not preserve_demo_prompts:
        for segment in demo_script:
            if segment["segment"] == "开场":
                segment["prompt"] = opening
            elif segment["segment"] in {"风险提示与结尾", "风险提示"} and duration == 60:
                segment["prompt"] = content_risk + closing
            elif segment["segment"] == "风险提示" and duration in {15, 30}:
                segment["prompt"] = content_risk + (closing if duration == 15 else "")
            elif segment["segment"] == "开场和判断":
                segment["prompt"] = content_open

    return {
        "voice_style": voice_style,
        "target_duration_sec": duration,
        "estimated_words": estimated_words,
        "compression_level": _compression_level(duration),
        "tone_notes": tone_notes,
        "use_case": use_case,
        "narration": {
            "duration_sec": duration_sec,
            "opening": opening,
            "script": script,
            "closing": closing,
        },
        "short_caption": short_caption,
        "demo_script": demo_script,
    }


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
    volatility_level = _volatility_level(volatility)
    liquidity_level = _liquidity_level(candidate)
    beginner = _beginner_friendly(volatility_level, liquidity_level, spread, candidate.change_24h)
    suggested_mode = _suggested_mode(volatility_level, liquidity_level, beginner)
    risk_score = _risk_score(volatility_level, liquidity_level, spread, candidate.change_24h)

    links = [
        item.get("link")
        for item in (meta.get("links") or [])
        if isinstance(item, dict) and item.get("link")
    ]
    notes = _risk_notes(candidate, volatility_level, liquidity_level, spread, beginner)
    risk_flags = _risk_flags(candidate, volatility_level, liquidity_level, spread, beginner)

    return {
        "symbol": candidate.symbol,
        "risk_score": risk_score,
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
        "volatility_risk": volatility_level,
        "liquidity_risk": liquidity_level,
        "beginner_friendly": beginner,
        "suggested_mode": suggested_mode,
        "risk_flags": risk_flags,
        "risk_summary": (
            f"{candidate.symbol} 当前波动风险为 {volatility_level}，"
            f"流动性风险为 {liquidity_level}，"
            f"更适合 {suggested_mode} 风格。"
        ),
        "notes": notes,
        "meta_excerpt": {
            "description": meta.get("description"),
            "creator_address": meta.get("creatorAddress"),
            "audit_info": meta.get("auditInfo"),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_trade_plan(risk_report: dict[str, Any], style: str) -> dict[str, Any]:
    normalized_style = style.strip().lower()
    if normalized_style not in STYLE_PRESETS:
        raise ValueError(f"unsupported style: {style}")

    preset = STYLE_PRESETS[normalized_style]
    price = float(risk_report["key_info"]["price"])
    volatility = float(risk_report["market_state"]["minute_volatility"])
    spread = float(risk_report["market_state"]["relative_spread"])
    beginner_friendly = bool(risk_report["beginner_friendly"])
    risk_score = int(risk_report["risk_score"])
    risk_flags = list(risk_report.get("risk_flags") or [])

    entry_pullback = preset["entry_pullback"] + min(volatility * 2.0, 0.08)
    entry_upper = price if normalized_style != "aggressive" else price * (1 + min(spread, 0.003))
    entry_lower = price * (1 - entry_pullback)
    entry_mid = (entry_upper + entry_lower) / 2

    stop_buffer = max(preset["min_stop"], volatility * 3.2 + spread * 2.0)
    stop_loss = entry_mid * (1 - stop_buffer)
    risk_per_unit = max(entry_mid - stop_loss, entry_mid * 0.01)
    take_profit_1 = entry_mid + risk_per_unit * preset["rr1"]
    take_profit_2 = entry_mid + risk_per_unit * preset["rr2"]

    position_pct = preset["position_pct"]
    if not beginner_friendly:
        position_pct *= 0.8
    if risk_score >= 70:
        position_pct *= 0.7
    elif risk_score <= 30:
        position_pct *= 1.1

    position_pct = max(0.005, min(position_pct, 0.04))
    confidence = int(max(5, min(95, 82 - risk_score * 0.45)))
    if normalized_style == risk_report.get("suggested_mode"):
        confidence = min(95, confidence + 10)
    elif normalized_style == "aggressive" and risk_report.get("suggested_mode") == "conservative":
        confidence = max(5, confidence - 15)
    elif normalized_style == "conservative" and risk_report.get("suggested_mode") == "aggressive":
        confidence = max(5, confidence - 12)
    if "illiquid" in risk_flags:
        confidence = max(5, confidence - 10)
    if "overheated" in risk_flags:
        confidence = max(5, confidence - 8)
    if "high_volatility" in risk_flags:
        confidence = max(5, confidence - 8)

    plan_reason_parts = []
    if normalized_style == risk_report.get("suggested_mode"):
        plan_reason_parts.append(f"当前风险结构与 {normalized_style} 风格匹配度较高。")
    else:
        plan_reason_parts.append(
            f"标的本身更偏向 {risk_report.get('suggested_mode')}，这里按 {normalized_style} 输出一版可执行参数。"
        )
    if risk_flags:
        plan_reason_parts.append(f"主要限制因素：{', '.join(risk_flags)}。")
    plan_reason_parts.append(f"建议仓位控制在 {position_pct * 100:.2f}% 左右。")

    return {
        "symbol": risk_report["symbol"],
        "style": normalized_style,
        "entry": {
            "buy_zone_low": _safe_round(entry_lower, 8),
            "buy_zone_high": _safe_round(entry_upper, 8),
            "reference_price": _safe_round(price, 8),
        },
        "stop_loss": _safe_round(stop_loss, 8),
        "take_profit": [
            _safe_round(take_profit_1, 8),
            _safe_round(take_profit_2, 8),
        ],
        "position_size": {
            "portfolio_pct": f"{position_pct * 100:.2f}%",
            "guidance": "单笔先按小仓位试错，连续失效时停止加仓。",
        },
        "invalidation": (
            f"若价格有效跌破 {_safe_round(stop_loss, 8)}，"
            "或盘口价差突然放大并伴随成交量衰减，则当前计划失效。"
        ),
        "confidence": confidence,
        "plan_reason": " ".join(plan_reason_parts),
        "execution_mode": "paper",
        "risk_note": (
            "该计划只用于研究和纸面推演，默认不自动转换成真实 Spot 或 Futures 订单。"
        ),
        "generated_from": {
            "risk_score": risk_report["risk_score"],
            "suggested_mode": risk_report["suggested_mode"],
            "minute_volatility": risk_report["market_state"]["minute_volatility"],
            "relative_spread": risk_report["market_state"]["relative_spread"],
        },
    }
