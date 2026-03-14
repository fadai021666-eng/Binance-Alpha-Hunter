"""测试 watchlist compare 逻辑。"""
from __future__ import annotations

from lib.watchlist import _status_change, _compare_watchlist


def test_status_change_new():
    assert _status_change(None, {"opportunity_score": 50}) == "new"


def test_status_change_missing():
    prev = {"opportunity_score": 50}
    current = {"status": "missing"}
    assert _status_change(prev, current) == "missing"


def test_status_change_improving():
    prev = {"opportunity_score": 40, "risk_score": 50, "tags": []}
    current = {"opportunity_score": 55, "risk_score": 45, "tags": []}
    assert _status_change(prev, current) == "improving"


def test_status_change_weakening():
    prev = {"opportunity_score": 60, "risk_score": 30, "tags": []}
    current = {"opportunity_score": 50, "risk_score": 30, "tags": []}
    assert _status_change(prev, current) == "weakening"


def test_status_change_tags_changed():
    prev = {"opportunity_score": 50, "risk_score": 50, "tags": ["hot"]}
    current = {"opportunity_score": 50, "risk_score": 50, "tags": ["hot", "new"]}
    assert _status_change(prev, current) == "tags_changed"


def test_status_change_stable():
    prev = {"opportunity_score": 50, "risk_score": 50, "tags": ["hot"]}
    current = {"opportunity_score": 52, "risk_score": 50, "tags": ["hot"]}
    assert _status_change(prev, current) == "stable"


def test_compare_watchlist_counts():
    previous = [
        {"symbol": "A", "opportunity_score": 40, "risk_score": 50, "tags": []},
    ]
    current = [
        {"symbol": "A", "opportunity_score": 55, "risk_score": 45, "tags": []},
        {"symbol": "B", "opportunity_score": 60, "risk_score": 30, "tags": ["hot"]},
    ]
    result = _compare_watchlist(current, previous)
    assert result["status_counts"]["improving"] == 1
    assert result["status_counts"]["new"] == 1
    assert len(result["items"]) == 2
