from __future__ import annotations

import gzip
import json
import random
import time
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .types import AlphaCandidate


BINANCE_BASE_URL = "https://www.binance.com"
BINANCE_WEB3_BASE_URL = "https://web3.binance.com"
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 0.6
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "identity",
}


class BinanceAlphaError(RuntimeError):
    pass


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _cache_path(cache_key: str) -> Path:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in cache_key)
    return CACHE_DIR / f"{sanitized}.json"


def _write_cache(cache_key: str, payload: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_key)
    wrapper = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    path.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_cache(cache_key: str) -> dict[str, Any] | None:
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError):
        return None
    if not isinstance(wrapper, dict) or "payload" not in wrapper:
        return None
    return wrapper


def _warning(message: str) -> list[str]:
    return [message]


def _merge_warnings(*warning_lists: list[str]) -> list[str]:
    merged: list[str] = []
    for warning_list in warning_lists:
        for item in warning_list:
            if item not in merged:
                merged.append(item)
    return merged


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code >= 500 or exc.code in {408, 409, 429}
    if isinstance(exc, (URLError, TimeoutError, JSONDecodeError, UnicodeDecodeError, EOFError, OSError)):
        message = str(exc).lower()
        retry_markers = [
            "unexpected eof",
            "timed out",
            "timeout",
            "temporary failure",
            "temporarily unavailable",
            "connection reset",
            "ssl",
            "eof occurred",
            "empty payload",
            "json",
        ]
        return any(marker in message for marker in retry_markers) or isinstance(
            exc, (TimeoutError, JSONDecodeError, UnicodeDecodeError, EOFError)
        )
    return False


def _decode_response(raw: bytes, encoding_header: str) -> dict[str, Any]:
    encoding = encoding_header.lower()
    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    if not raw:
        raise ValueError("empty payload")
    return json.loads(raw.decode("utf-8"))


def _request_json(
    base_url: str,
    path: str,
    params: dict[str, Any] | None = None,
    *,
    cache_key: str | None = None,
    allow_cache_fallback: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(url, headers=DEFAULT_HEADERS)
    warnings: list[str] = []
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read()
                payload = _decode_response(raw, str(response.headers.get("Content-Encoding") or ""))
            if cache_key:
                _write_cache(cache_key, payload)
            return payload, {
                "data_source": "live",
                "stale": False,
                "fetch_warnings": warnings,
                "cache_key": cache_key,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < MAX_RETRIES and _is_retryable(exc):
                warnings.append(f"{path} 第 {attempt} 次请求失败，正在重试：{exc}")
                sleep_seconds = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)) + random.uniform(0.05, 0.25)
                time.sleep(sleep_seconds)
                continue
            break

    if allow_cache_fallback and cache_key:
        cached = _read_cache(cache_key)
        if cached is not None:
            warnings.append(f"{path} 实时请求失败，已回退到本地缓存。")
            return cached["payload"], {
                "data_source": "cache_fallback",
                "stale": True,
                "fetch_warnings": warnings,
                "cache_key": cache_key,
                "cached_at": cached.get("cached_at"),
            }

    if isinstance(last_error, HTTPError):
        body = last_error.read().decode("utf-8", "ignore")
        raise BinanceAlphaError(f"HTTP {last_error.code} for {url}: {body[:300]}") from last_error
    if last_error is not None:
        raise BinanceAlphaError(f"request failed for {url}: {last_error}") from last_error
    raise BinanceAlphaError(f"request failed for {url}: unknown error")


def _validate_payload(payload: dict[str, Any], url: str) -> None:
    code = payload.get("code")
    if payload.get("success") is False or code not in (None, "000000"):
        raise BinanceAlphaError(f"unexpected Binance payload for {url}: {payload}")


def _finalize_meta(*metas: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    stale = False
    data_source = "live"
    for meta in metas:
        warnings = _merge_warnings(warnings, meta.get("fetch_warnings") or [])
        if meta.get("stale"):
            stale = True
            data_source = "cache_fallback"
    return {
        "data_source": data_source,
        "stale": stale,
        "fetch_warnings": warnings,
    }


def fetch_token_list(include_meta: bool = False) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    payload, meta = _request_json(
        BINANCE_BASE_URL,
        "/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list",
        cache_key="alpha-token-list",
    )
    _validate_payload(payload, "token_list")
    data = payload.get("data") or []
    if not isinstance(data, list):
        raise BinanceAlphaError("token list format error")
    return (data, meta) if include_meta else data


def fetch_exchange_info(include_meta: bool = False) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    payload, meta = _request_json(
        BINANCE_BASE_URL,
        "/bapi/defi/v1/public/alpha-trade/get-exchange-info",
        cache_key="alpha-exchange-info",
    )
    _validate_payload(payload, "exchange_info")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise BinanceAlphaError("exchange info format error")
    return (data, meta) if include_meta else data


def fetch_klines(
    market_symbol: str,
    interval: str = "1m",
    limit: int = 60,
    include_meta: bool = False,
) -> list[list[Any]] | tuple[list[list[Any]], dict[str, Any]]:
    cache_key = f"klines_{market_symbol}_{interval}_{limit}"
    payload, meta = _request_json(
        BINANCE_BASE_URL,
        "/bapi/defi/v1/public/alpha-trade/klines",
        params={"symbol": market_symbol, "interval": interval, "limit": limit},
        cache_key=cache_key,
    )
    _validate_payload(payload, f"klines:{market_symbol}")
    data = payload.get("data") or []
    if not isinstance(data, list):
        raise BinanceAlphaError(f"klines format error for {market_symbol}")
    return (data, meta) if include_meta else data


def fetch_book_ticker(
    market_symbol: str,
    include_meta: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    cache_key = f"book-ticker_{market_symbol}"
    payload, meta = _request_json(
        BINANCE_BASE_URL,
        "/bapi/defi/v1/public/alpha-trade/book-ticker",
        params={"symbol": market_symbol},
        cache_key=cache_key,
    )
    _validate_payload(payload, f"book_ticker:{market_symbol}")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise BinanceAlphaError(f"book ticker format error for {market_symbol}")
    return (data, meta) if include_meta else data


def fetch_token_meta(
    chain_id: str,
    contract_address: str,
    include_meta: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    cache_key = f"token-meta_{chain_id}_{contract_address}"
    payload, meta = _request_json(
        BINANCE_WEB3_BASE_URL,
        "/bapi/defi/v1/public/wallet-direct/buw/wallet/dex/market/token/meta/info",
        params={"chainId": chain_id, "contractAddress": contract_address},
        cache_key=cache_key,
    )
    _validate_payload(payload, f"token_meta:{contract_address}")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise BinanceAlphaError(f"token meta format error for {contract_address}")
    return (data, meta) if include_meta else data


def _build_pair_map(symbols: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    pair_map: dict[str, dict[str, Any]] = {}
    quote_priority = {"USDT": 0, "USDC": 1}

    for item in symbols:
        if item.get("status") != "TRADING":
            continue

        base_asset = item.get("baseAsset")
        quote_asset = item.get("quoteAsset")
        if not base_asset or quote_asset not in quote_priority:
            continue

        current = pair_map.get(base_asset)
        if current is None or quote_priority[quote_asset] < quote_priority[current["quoteAsset"]]:
            pair_map[base_asset] = {
                "symbol": item["symbol"],
                "quoteAsset": quote_asset,
            }

    return pair_map


def _extract_tags(token: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if int(token.get("mulPoint") or 0) == 4:
        tags.append("4x积分")
    if token.get("hotTag"):
        tags.append("热门")
    if token.get("onlineAirdrop"):
        tags.append("空投")
    if token.get("onlineTge"):
        tags.append("TGE")
    if token.get("bnExclusiveState"):
        tags.append("Binance专属")
    if token.get("chainName"):
        tags.append(str(token["chainName"]))
    return tags


def _candidate_from_payload(token: dict[str, Any], pair: dict[str, Any]) -> AlphaCandidate:
    token_symbol = str(token.get("symbol") or token.get("alphaId") or "")
    quote_asset = str(pair.get("quoteAsset") or "USDT")
    display_symbol = f"{token_symbol}{quote_asset}"
    return AlphaCandidate(
        symbol=display_symbol,
        name=str(token.get("name") or token_symbol),
        token_symbol=token_symbol,
        alpha_id=str(token.get("alphaId") or ""),
        market_symbol=str(pair.get("symbol") or ""),
        chain_id=str(token.get("chainId") or ""),
        chain_name=str(token.get("chainName") or ""),
        contract_address=str(token.get("contractAddress") or ""),
        price=_to_float(token.get("price")),
        change_24h=_to_float(token.get("percentChange24h")),
        volume_24h=_to_float(token.get("volume24h")),
        liquidity=_to_float(token.get("liquidity")),
        market_cap=_to_float(token.get("marketCap")),
        fdv=_to_float(token.get("fdv")),
        holders=_to_int(token.get("holders")),
        listing_time_ms=_to_int(token.get("listingTime")),
        tags=_extract_tags(token),
    )


def _candidate_from_dict(payload: dict[str, Any]) -> AlphaCandidate:
    return AlphaCandidate(
        symbol=str(payload.get("symbol") or ""),
        name=str(payload.get("name") or ""),
        token_symbol=str(payload.get("token_symbol") or ""),
        alpha_id=str(payload.get("alpha_id") or ""),
        market_symbol=str(payload.get("market_symbol") or ""),
        chain_id=str(payload.get("chain_id") or ""),
        chain_name=str(payload.get("chain_name") or ""),
        contract_address=str(payload.get("contract_address") or ""),
        price=_to_float(payload.get("price")),
        change_24h=_to_float(payload.get("change_24h")),
        volume_24h=_to_float(payload.get("volume_24h")),
        liquidity=_to_float(payload.get("liquidity")),
        market_cap=_to_float(payload.get("market_cap")),
        fdv=_to_float(payload.get("fdv")),
        holders=_to_int(payload.get("holders")),
        listing_time_ms=_to_int(payload.get("listing_time_ms")),
        tags=list(payload.get("tags") or []),
    )


def list_alpha_candidates(
    limit: int | None = 20,
    sort_by: str = "volume",
    include_meta: bool = False,
) -> list[AlphaCandidate] | tuple[list[AlphaCandidate], dict[str, Any]]:
    cache_key = "alpha_candidates"
    try:
        token_list, token_meta = fetch_token_list(include_meta=True)
        exchange_info, exchange_meta = fetch_exchange_info(include_meta=True)
        pair_map = _build_pair_map(exchange_info.get("symbols") or [])

        candidates: list[AlphaCandidate] = []
        for token in token_list:
            if int(token.get("mulPoint") or 0) != 4:
                continue
            if token.get("offline") or token.get("offsell") or token.get("cexOffDisplay"):
                continue

            alpha_id = token.get("alphaId")
            pair = pair_map.get(alpha_id)
            if not alpha_id or not pair:
                continue

            candidates.append(_candidate_from_payload(token, pair))

        sort_key = sort_by.lower().strip()
        if sort_key == "change":
            candidates.sort(key=lambda item: abs(item.change_24h), reverse=True)
        elif sort_key in {"new", "listed", "listing"}:
            candidates.sort(key=lambda item: item.listing_time_ms or 0, reverse=True)
        elif sort_key == "liquidity":
            candidates.sort(key=lambda item: item.liquidity, reverse=True)
        else:
            candidates.sort(key=lambda item: item.volume_24h, reverse=True)

        _write_cache(cache_key, [candidate.to_full_dict() for candidate in candidates])
        meta = _finalize_meta(token_meta, exchange_meta)
    except BinanceAlphaError as exc:
        cached = _read_cache(cache_key)
        if cached is None:
            raise
        candidates = [_candidate_from_dict(item) for item in (cached.get("payload") or [])]
        meta = {
            "data_source": "cache_fallback",
            "stale": True,
            "fetch_warnings": _warning(f"候选列表实时刷新失败，已回退到缓存：{exc}"),
            "cached_at": cached.get("cached_at"),
        }

    if limit is not None and limit > 0:
        candidates = candidates[:limit]
    return (candidates, meta) if include_meta else candidates


def normalize_symbol(text: str) -> str:
    return text.strip().upper().replace("/", "").replace("-", "").replace("_", "")


def resolve_candidate(query: str, include_meta: bool = False) -> AlphaCandidate | tuple[AlphaCandidate, dict[str, Any]]:
    normalized = normalize_symbol(query)
    candidates, meta = list_alpha_candidates(limit=None, sort_by="volume", include_meta=True)

    exact_fields = (
        "symbol",
        "token_symbol",
        "alpha_id",
        "market_symbol",
        "contract_address",
    )
    for candidate in candidates:
        for field in exact_fields:
            value = getattr(candidate, field)
            if normalize_symbol(str(value)) == normalized:
                return (candidate, meta) if include_meta else candidate

    for candidate in candidates:
        if normalized in normalize_symbol(candidate.name) or normalized in normalize_symbol(candidate.token_symbol):
            return (candidate, meta) if include_meta else candidate

    raise BinanceAlphaError(f"未找到 Alpha 标的: {query}")


def get_candidate_snapshot(query: str, kline_limit: int = 60) -> dict[str, Any]:
    candidate, candidate_meta = resolve_candidate(query, include_meta=True)
    warnings = list(candidate_meta.get("fetch_warnings") or [])
    stale = bool(candidate_meta.get("stale"))
    data_source = str(candidate_meta.get("data_source") or "live")

    try:
        token_meta, token_meta_meta = fetch_token_meta(candidate.chain_id, candidate.contract_address, include_meta=True)
    except BinanceAlphaError as exc:
        token_meta = {}
        token_meta_meta = {
            "data_source": "cache_fallback",
            "stale": True,
            "fetch_warnings": _warning(f"{candidate.symbol} 的 token meta 拉取失败，已降级为空：{exc}"),
        }
    try:
        klines, kline_meta = fetch_klines(candidate.market_symbol, limit=kline_limit, include_meta=True)
    except BinanceAlphaError as exc:
        klines = []
        kline_meta = {
            "data_source": "cache_fallback",
            "stale": True,
            "fetch_warnings": _warning(f"{candidate.symbol} 的 klines 拉取失败，已降级为空：{exc}"),
        }
    try:
        book_ticker, book_meta = fetch_book_ticker(candidate.market_symbol, include_meta=True)
    except BinanceAlphaError as exc:
        book_ticker = {}
        book_meta = {
            "data_source": "cache_fallback",
            "stale": True,
            "fetch_warnings": _warning(f"{candidate.symbol} 的 book ticker 拉取失败，已降级为空：{exc}"),
        }

    combined_meta = _finalize_meta(candidate_meta, token_meta_meta, kline_meta, book_meta)
    warnings = _merge_warnings(warnings, combined_meta.get("fetch_warnings") or [])
    stale = stale or bool(combined_meta.get("stale"))
    if combined_meta.get("data_source") == "cache_fallback":
        data_source = "cache_fallback"

    return {
        "candidate": candidate,
        "meta": token_meta,
        "klines": klines,
        "book_ticker": book_ticker,
        "fetch_meta": {
            "data_source": data_source,
            "stale": stale,
            "fetch_warnings": warnings,
        },
    }
