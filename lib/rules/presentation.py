"""展示摘要与旁白生成逻辑。"""
from __future__ import annotations

import statistics
from typing import Any


VOICE_STYLES = {"neutral", "energetic", "competition"}
DURATION_CHOICES = {15, 30, 60}


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
        if ch.strip() and ch not in "，。！？；：、""''（）()【】[]《》…,.!?;:-"
    ]
    return max(1, round(len(filtered) * 0.7))


def _compression_level(duration: int) -> str:
    if duration <= 15:
        return "high"
    if duration <= 30:
        return "medium"
    return "low"


def _build_content_blocks(
    presentation: dict[str, Any],
    duration: int,
    data_status: dict[str, Any],
) -> dict[str, str]:
    """构建各时长的内容块：open / body / watch / risk。"""
    top_picks = list(presentation.get("top_picks") or [])
    watch_only = list(presentation.get("watch_only") or [])
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

    short_market_view = market_view.split("。", 1)[0] + "。" if "。" in market_view else market_view
    short_risk_notice = risk_notice.split("；", 1)[0] + "。" if "；" in risk_notice else risk_notice
    primary_pick = top_picks[0]["symbol"] if top_picks else "当前以观察为主"

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
    elif duration == 60:
        content_open = market_view
        content_body = top_pick_line
        if top_pick_reason_line_1:
            content_body += top_pick_reason_line_1
        if top_pick_reason_line_2:
            content_body += " " + top_pick_reason_line_2
        content_watch = watch_line
        content_risk = risk_notice + data_status_line + "这份结果不是只给数据，也是在强调执行前的筛选和风控。"
    else:
        content_open = market_view
        content_body = "今天优先讲的标的是" + "、".join(
            f"{item['symbol']}（{item['verdict']}）" for item in top_picks[:2]
        ) + "。" if top_picks else top_pick_line
        if top_pick_reason_line_1:
            content_body += top_pick_reason_line_1
        content_watch = watch_line
        content_risk = risk_notice + data_status_line

    return {
        "open": content_open,
        "body": content_body,
        "watch": content_watch,
        "risk": content_risk,
        "market_view": market_view,
        "risk_notice": risk_notice,
        "top_pick_line": top_pick_line,
        "top_pick_reason_line_1": top_pick_reason_line_1,
        "top_pick_reason_line_2": top_pick_reason_line_2,
        "watch_line": watch_line,
        "data_status_line": data_status_line,
    }


def _build_demo_script_15(content: dict[str, str], market_view: str, risk_notice: str) -> list[dict[str, str]]:
    return [
        {"segment": "开场", "seconds": "0-2", "prompt": ""},
        {"segment": "开场和判断", "seconds": "0-5", "prompt": market_view},
        {"segment": "重点标的", "seconds": "5-10", "prompt": content["body"]},
        {"segment": "风险提示", "seconds": "10-15", "prompt": risk_notice},
    ]


def _build_demo_script_30(content: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"segment": "开场", "seconds": "0-5", "prompt": ""},
        {"segment": "市场判断", "seconds": "5-12", "prompt": content["open"]},
        {"segment": "重点标的", "seconds": "12-22", "prompt": content["body"]},
        {"segment": "观察名单", "seconds": "22-27", "prompt": content["watch"]},
        {"segment": "风险提示", "seconds": "27-30", "prompt": content["risk"]},
    ]


def _build_demo_script_60(content: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"segment": "开场", "seconds": "0-8", "prompt": ""},
        {"segment": "市场判断", "seconds": "8-20", "prompt": content["open"]},
        {"segment": "重点标的", "seconds": "20-42", "prompt": content["body"]},
        {"segment": "观察名单", "seconds": "42-52", "prompt": content["watch"]},
        {"segment": "风险提示与结尾", "seconds": "52-60", "prompt": content["risk"]},
    ]


def _build_style_neutral(
    content: dict[str, str],
    mode: str,
    duration: int,
    top_symbols: str,
    degraded_components_zh: list[str],
) -> dict[str, str]:
    opening = f"这是一版 Binance Alpha Hunter 的 {mode} 模式展示。"
    script = (
        f"{content['open']}"
        f"{content['body']}"
        f"{content['watch']}"
        f"{content['risk']}"
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
    return {
        "opening": opening,
        "script": script,
        "closing": closing,
        "short_caption": short_caption,
        "tone_notes": "客观、平稳、信息密度适中，适合常规产品演示和讲解。",
        "use_case": "适合常规产品演示、日常录屏讲解、稳态说明。",
    }


def _build_style_energetic(
    content: dict[str, str],
    mode: str,
    duration: int,
    top_symbols: str,
    degraded_components_zh: list[str],
) -> dict[str, str]:
    opening = f"下面这版是 Binance Alpha Hunter 的 {mode} 高节奏展示，我们直接看机会点。"
    script = (
        f"{content['open']}"
        f"{content['body']}"
        f"{content['watch']}"
        f"{content['risk']}"
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
    return {
        "opening": opening,
        "script": script,
        "closing": closing,
        "short_caption": short_caption,
        "tone_notes": "节奏更快，更有推进感，适合短视频、宣传片段、录屏亮点展示。",
        "use_case": "适合短视频、宣传展示、节奏更快的录屏解说。",
    }


def _build_style_competition(
    content: dict[str, str],
    presentation: dict[str, Any],
    mode: str,
    duration: int,
    top_symbols: str,
    degraded_components_zh: list[str],
) -> tuple[dict[str, str], list[dict[str, str]] | None]:
    """返回 (style_dict, override_demo_script_or_None)。"""
    top_picks = list(presentation.get("top_picks") or [])
    watch_only = list(presentation.get("watch_only") or [])

    opening = f"这是 Binance Alpha Hunter 的 {mode} 比赛展示，重点看机会发现和风控闭环。"
    override_demo = None

    if duration == 60:
        competition_picks = "、".join(
            f"{item['symbol']}（{item['verdict']}）" for item in top_picks[:2]
        ) or top_symbols
        competition_pick_reason = ""
        if top_picks:
            competition_pick_reason = f"{top_picks[0]['symbol']} 的理由是{top_picks[0].get('summary') or ''}"
        if len(top_picks) > 1:
            competition_pick_reason += f"{top_picks[1]['symbol']} 则是{top_picks[1].get('summary') or ''}"
        watch_line = content["watch_line"]
        short_risk_notice = content["risk_notice"].split("；", 1)[0] + "。" if "；" in content["risk_notice"] else content["risk_notice"]
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
            f"{content['open']}"
            f"这轮优先看 {competition_picks}。"
            f"{competition_pick_reason}"
            f"{competition_risk_line}"
            f"{competition_data_line}"
            "这份结果已经把发现、筛选和执行前风控串成闭环。"
        ).strip()
        override_demo = [
            {"segment": "开场", "seconds": "0-8", "prompt": opening},
            {"segment": "市场判断", "seconds": "8-18", "prompt": content["open"]},
            {"segment": "重点标的", "seconds": "18-36", "prompt": f"这轮优先看 {competition_picks}。{competition_pick_reason}"},
            {"segment": "观察名单", "seconds": "36-46", "prompt": competition_risk_line},
            {"segment": "风险提示与结尾", "seconds": "46-60", "prompt": f"{competition_data_line}{opening}"},
        ]
    else:
        script = (
            f"{content['open']}"
            f"{content['body']}"
            f"{content['watch']}"
            f"{content['risk']}"
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
    short_caption = (
        f"Binance Alpha Hunter 作品展示：{mode} 模式下重点关注 {top_symbols}。"
        "不仅发现机会，也把风险和执行边界说明白。"
        + (" 当前含降级回退。" if degraded_components_zh else " 当前数据链路正常。")
    )
    style_dict = {
        "opening": opening,
        "script": script,
        "closing": closing,
        "short_caption": short_caption,
        "tone_notes": "更强调方法价值、机会发现、风险控制和产出闭环，适合比赛投稿。",
        "use_case": "适合作品投稿、比赛答辩、强调方法论和闭环能力的演示。",
    }
    return style_dict, override_demo


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
    mode = presentation.get("mode", "momentum")
    data_status = data_status or {}
    degraded_components_zh = list(data_status.get("degraded_components_zh") or [])

    top_symbols = "、".join(item["symbol"] for item in top_picks[:3]) or "当前以观察为主"
    content = _build_content_blocks(presentation, duration, data_status)

    # 默认 demo_script
    if duration == 15:
        demo_script = _build_demo_script_15(content, content["market_view"], content["risk_notice"])
    elif duration == 60:
        demo_script = _build_demo_script_60(content)
    else:
        demo_script = _build_demo_script_30(content)

    # 按风格生成文案
    preserve_demo_prompts = False
    if voice_style == "energetic":
        style_result = _build_style_energetic(content, mode, duration, top_symbols, degraded_components_zh)
    elif voice_style == "competition":
        style_result, override_demo = _build_style_competition(
            content, presentation, mode, duration, top_symbols, degraded_components_zh,
        )
        if override_demo is not None:
            demo_script = override_demo
            preserve_demo_prompts = True
    else:
        style_result = _build_style_neutral(content, mode, duration, top_symbols, degraded_components_zh)

    opening = style_result["opening"]
    script = style_result["script"].replace("。。", "。").replace("..", ".").strip()
    closing = style_result["closing"]

    estimated_words = _estimate_spoken_words(opening + script + closing)

    if not preserve_demo_prompts:
        for segment in demo_script:
            if segment["segment"] == "开场":
                segment["prompt"] = opening
            elif segment["segment"] in {"风险提示与结尾", "风险提示"} and duration == 60:
                segment["prompt"] = content["risk"] + closing
            elif segment["segment"] == "风险提示" and duration in {15, 30}:
                segment["prompt"] = content["risk"] + (closing if duration == 15 else "")
            elif segment["segment"] == "开场和判断":
                segment["prompt"] = content["open"]

    return {
        "voice_style": voice_style,
        "target_duration_sec": duration,
        "estimated_words": estimated_words,
        "compression_level": _compression_level(duration),
        "tone_notes": style_result["tone_notes"],
        "use_case": style_result["use_case"],
        "narration": {
            "duration_sec": duration,
            "opening": opening,
            "script": script,
            "closing": closing,
        },
        "short_caption": style_result["short_caption"],
        "demo_script": demo_script,
    }
