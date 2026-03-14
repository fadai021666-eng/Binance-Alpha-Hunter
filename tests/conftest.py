"""共享 fixtures。"""
from __future__ import annotations

import pytest

from lib.types import AlphaCandidate


@pytest.fixture()
def make_candidate():
    """工厂函数，快速构建 AlphaCandidate。"""
    def _factory(**overrides) -> AlphaCandidate:
        defaults = dict(
            symbol="TESTUSDT",
            name="Test Token",
            token_symbol="TEST",
            alpha_id="TEST",
            market_symbol="TESTUSDT",
            chain_id="56",
            chain_name="BSC",
            contract_address="0x" + "a" * 40,
            price=1.0,
            change_24h=5.0,
            volume_24h=2_000_000.0,
            liquidity=1_500_000.0,
            market_cap=10_000_000.0,
            fdv=20_000_000.0,
            holders=1000,
            listing_time_ms=None,
            tags=["4x积分"],
        )
        defaults.update(overrides)
        return AlphaCandidate(**defaults)
    return _factory


@pytest.fixture()
def sample_klines():
    """30 根 1m K线，close 从 1.0 缓慢上涨到 ~1.03。"""
    klines = []
    for i in range(30):
        t = 1700000000000 + i * 60000
        o = 1.0 + i * 0.001
        h = o + 0.002
        low = o - 0.001
        c = o + 0.001
        v = 10000 + i * 100
        klines.append([t, str(o), str(h), str(low), str(c), str(v)])
    return klines


@pytest.fixture()
def sample_book_ticker():
    return {"bidPrice": "1.028", "askPrice": "1.032"}


@pytest.fixture()
def sample_risk_report(make_candidate, sample_klines, sample_book_ticker):
    from lib.rules import build_risk_report
    candidate = make_candidate()
    return build_risk_report(candidate, {}, sample_klines, sample_book_ticker)
