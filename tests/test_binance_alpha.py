"""测试 binance_alpha 网络层辅助函数。"""
from __future__ import annotations

import gzip
import json
from urllib.error import HTTPError

from lib.binance_alpha import _is_retryable, _decode_response, normalize_symbol


def test_is_retryable_500():
    err = HTTPError("http://x", 500, "err", {}, None)
    assert _is_retryable(err) is True


def test_is_retryable_429():
    err = HTTPError("http://x", 429, "err", {}, None)
    assert _is_retryable(err) is True


def test_is_retryable_404():
    err = HTTPError("http://x", 404, "err", {}, None)
    assert _is_retryable(err) is False


def test_is_retryable_timeout():
    assert _is_retryable(TimeoutError("timed out")) is True


def test_is_retryable_eof():
    assert _is_retryable(EOFError("unexpected eof")) is True


def test_decode_response_plain():
    data = {"key": "value"}
    raw = json.dumps(data).encode("utf-8")
    result = _decode_response(raw, "")
    assert result == data


def test_decode_response_gzip():
    data = {"key": "gzipped"}
    raw = gzip.compress(json.dumps(data).encode("utf-8"))
    result = _decode_response(raw, "gzip")
    assert result == data


def test_decode_response_gzip_by_magic():
    data = {"key": "auto"}
    raw = gzip.compress(json.dumps(data).encode("utf-8"))
    result = _decode_response(raw, "identity")
    assert result == data


def test_decode_response_empty_raises():
    import pytest
    with pytest.raises(ValueError, match="empty"):
        _decode_response(b"", "")


def test_normalize_symbol():
    assert normalize_symbol("  test/usdt ") == "TESTUSDT"
    assert normalize_symbol("BTC-USDT") == "BTCUSDT"
    assert normalize_symbol("eth_usdc") == "ETHUSDC"
