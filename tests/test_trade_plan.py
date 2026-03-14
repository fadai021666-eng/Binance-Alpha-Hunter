"""测试 build_trade_plan。"""
from __future__ import annotations

import pytest

from lib.rules import build_trade_plan


def test_entry_zone_math(sample_risk_report):
    plan = build_trade_plan(sample_risk_report, "balanced")
    entry = plan["entry"]
    assert entry["buy_zone_low"] <= entry["reference_price"]
    assert entry["buy_zone_high"] >= entry["buy_zone_low"]


def test_stop_loss_below_entry(sample_risk_report):
    plan = build_trade_plan(sample_risk_report, "balanced")
    assert plan["stop_loss"] < plan["entry"]["buy_zone_low"]


def test_take_profit_above_entry(sample_risk_report):
    plan = build_trade_plan(sample_risk_report, "balanced")
    tp = plan["take_profit"]
    assert len(tp) == 2
    assert tp[0] > plan["entry"]["buy_zone_high"]
    assert tp[1] > tp[0]


def test_confidence_range(sample_risk_report):
    for style in ("conservative", "balanced", "aggressive"):
        plan = build_trade_plan(sample_risk_report, style)
        assert 5 <= plan["confidence"] <= 95


def test_position_pct_range(sample_risk_report):
    for style in ("conservative", "balanced", "aggressive"):
        plan = build_trade_plan(sample_risk_report, style)
        pct_str = plan["position_size"]["portfolio_pct"]
        pct = float(pct_str.rstrip("%"))
        assert 0.5 <= pct <= 4.0


def test_invalid_style_raises(sample_risk_report):
    with pytest.raises(ValueError, match="unsupported"):
        build_trade_plan(sample_risk_report, "yolo")


def test_all_styles_produce_plan(sample_risk_report):
    for style in ("conservative", "balanced", "aggressive"):
        plan = build_trade_plan(sample_risk_report, style)
        assert plan["symbol"] == sample_risk_report["symbol"]
        assert plan["style"] == style
