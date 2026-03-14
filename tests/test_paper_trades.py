"""测试 paper trade 读写和归一化。"""
from __future__ import annotations

from lib.paper_trades import normalize_trade_record, build_recent_trade_summary


def test_normalize_fills_defaults():
    record = {"symbol": "TESTUSDT"}
    result = normalize_trade_record(record, 0)
    assert result["trade_id"] == "legacy-1"
    assert result["action"] == "buy"
    assert result["style"] == "balanced"
    assert result["mode"] == "paper"
    assert "execution_summary" in result


def test_normalize_preserves_existing():
    record = {
        "trade_id": "paper-123",
        "symbol": "XUSDT",
        "action": "sell",
        "style": "aggressive",
        "execution_summary": "custom summary",
    }
    result = normalize_trade_record(record, 5)
    assert result["trade_id"] == "paper-123"
    assert result["action"] == "sell"
    assert result["execution_summary"] == "custom summary"


def test_normalize_handles_bad_risk_report():
    record = {"symbol": "BAD", "risk_report": "not a dict"}
    result = normalize_trade_record(record, 0)
    assert result["risk_report"] == {}
    assert result["risk_flags"] == []


def test_build_recent_trade_summary_empty():
    assert build_recent_trade_summary([]) is None


def test_build_recent_trade_summary_returns_latest():
    records = [
        {"symbol": "A", "trade_id": "t1", "created_at": "2025-01-02"},
        {"symbol": "A", "trade_id": "t2", "created_at": "2025-01-01"},
        {"symbol": "B", "trade_id": "t3", "created_at": "2025-01-01"},
    ]
    summary = build_recent_trade_summary(records)
    assert summary is not None
    assert summary["symbol"] == "A"
    assert summary["latest_trade_id"] == "t1"
    assert len(summary["top_symbols"]) <= 3
