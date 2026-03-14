"""交易计划生成逻辑。"""
from __future__ import annotations

from typing import Any


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


def _safe_round(value: float, digits: int = 8) -> float:
    return round(float(value), digits)


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
