"""Binance Alpha Hunter 规则引擎。

拆分为子模块，此处统一 re-export 保持向后兼容。
"""
from .discover import (
    DISCOVER_MODES,
    build_discover_candidates,
    compute_kline_metrics,
)
from .presentation import (
    DURATION_CHOICES,
    VOICE_STYLES,
    build_narration_bundle,
    build_presentation_summary,
)
from .risk import (
    build_risk_report,
    compute_relative_spread,
    compute_volatility,
)
from .trade_plan import (
    STYLE_PRESETS,
    build_trade_plan,
)

__all__ = [
    "DISCOVER_MODES",
    "DURATION_CHOICES",
    "STYLE_PRESETS",
    "VOICE_STYLES",
    "build_discover_candidates",
    "build_narration_bundle",
    "build_presentation_summary",
    "build_risk_report",
    "build_trade_plan",
    "compute_kline_metrics",
    "compute_relative_spread",
    "compute_volatility",
]
