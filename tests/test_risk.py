"""测试 build_risk_report。"""
from __future__ import annotations

from lib.rules import build_risk_report


def test_risk_score_range(make_candidate, sample_klines, sample_book_ticker):
    candidate = make_candidate()
    report = build_risk_report(candidate, {}, sample_klines, sample_book_ticker)
    assert 0 <= report["risk_score"] <= 100


def test_volatility_levels(make_candidate, sample_book_ticker):
    flat_klines = [[0, "1", "1.001", "0.999", "1.0", "1000"]] * 30
    report = build_risk_report(make_candidate(), {}, flat_klines, sample_book_ticker)
    assert report["volatility_risk"] in ("low", "medium", "high")


def test_beginner_friendly_low_vol(make_candidate, sample_book_ticker):
    flat_klines = [[0, "1", "1.001", "0.999", "1.0", "1000"]] * 30
    candidate = make_candidate(
        volume_24h=6_000_000, liquidity=3_000_000, change_24h=2.0,
    )
    report = build_risk_report(candidate, {}, flat_klines, {"bidPrice": "1.0", "askPrice": "1.002"})
    assert report["beginner_friendly"] is True


def test_beginner_unfriendly_high_vol(make_candidate, sample_book_ticker):
    wild_klines = []
    for i in range(30):
        c = 1.0 + (i % 2) * 0.05
        wild_klines.append([0, str(c), str(c + 0.02), str(c - 0.02), str(c), "5000"])
    candidate = make_candidate(volume_24h=300_000, liquidity=100_000, change_24h=50.0)
    report = build_risk_report(candidate, {}, wild_klines, sample_book_ticker)
    assert report["beginner_friendly"] is False


def test_risk_flags_present(make_candidate, sample_book_ticker):
    candidate = make_candidate(volume_24h=200_000, liquidity=100_000, change_24h=50.0)
    report = build_risk_report(candidate, {}, [], sample_book_ticker)
    assert "illiquid" in report["risk_flags"]
    assert "overheated" in report["risk_flags"]


def test_suggested_mode_values(make_candidate, sample_klines, sample_book_ticker):
    report = build_risk_report(make_candidate(), {}, sample_klines, sample_book_ticker)
    assert report["suggested_mode"] in ("conservative", "balanced", "aggressive")


def test_empty_klines_and_book(make_candidate):
    report = build_risk_report(make_candidate(), {}, [], {})
    assert report["volatility_risk"] == "low"
    assert report["market_state"]["relative_spread"] == 0.0
