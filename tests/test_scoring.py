"""测试 build_discover_candidates 打分逻辑。"""
from __future__ import annotations

from lib.rules import build_discover_candidates


def test_score_range(make_candidate, sample_klines):
    candidates = [make_candidate(symbol=f"T{i}USDT", change_24h=i * 3 - 10) for i in range(10)]
    kline_map = {c.symbol: sample_klines for c in candidates}
    results = build_discover_candidates(candidates, kline_map, "momentum")
    for item in results:
        assert 0 <= item["opportunity_score"] <= 100, f"{item['symbol']} score out of range"


def test_sort_by_score(make_candidate, sample_klines):
    c1 = make_candidate(symbol="HIGHUSDT", change_24h=15, volume_24h=8_000_000, liquidity=3_000_000)
    c2 = make_candidate(symbol="LOWUSDT", change_24h=-20, volume_24h=500_000, liquidity=200_000)
    klines = {c1.symbol: sample_klines, c2.symbol: sample_klines}
    results = build_discover_candidates([c1, c2], klines, "momentum")
    result_map = {r["symbol"]: r for r in results}
    assert result_map["HIGHUSDT"]["opportunity_score"] > result_map["LOWUSDT"]["opportunity_score"]


def test_mode_filter_contrarian(make_candidate, sample_klines):
    c = make_candidate(symbol="DIPUSDT", change_24h=-10, volume_24h=2_000_000, liquidity=1_000_000)
    results = build_discover_candidates([c], {c.symbol: sample_klines}, "contrarian")
    assert results[0]["mode_match"] is True


def test_mode_filter_momentum_rejects_illiquid(make_candidate, sample_klines):
    c = make_candidate(symbol="WEAKUSDT", change_24h=10, volume_24h=100_000, liquidity=100_000)
    results = build_discover_candidates([c], {c.symbol: sample_klines}, "momentum")
    assert results[0]["mode_match"] is False


def test_empty_klines(make_candidate):
    c = make_candidate()
    results = build_discover_candidates([c], {}, "momentum")
    assert len(results) == 1
    assert 0 <= results[0]["opportunity_score"] <= 100


def test_all_modes_produce_results(make_candidate, sample_klines):
    c = make_candidate()
    for mode in ("momentum", "safe", "early", "contrarian"):
        results = build_discover_candidates([c], {c.symbol: sample_klines}, mode)
        assert len(results) == 1


def test_invalid_mode_raises(make_candidate):
    import pytest
    with pytest.raises(ValueError, match="unsupported"):
        build_discover_candidates([make_candidate()], {}, "invalid_mode")
