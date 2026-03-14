from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _round_or_none(value: float | None, digits: int = 8) -> float | None:
    if value is None:
        return None
    return round(value, digits)


@dataclass(slots=True)
class AlphaCandidate:
    symbol: str
    name: str
    token_symbol: str
    alpha_id: str
    market_symbol: str
    chain_id: str
    chain_name: str
    contract_address: str
    price: float
    change_24h: float
    volume_24h: float
    liquidity: float
    market_cap: float
    fdv: float
    holders: int | None
    listing_time_ms: int | None
    tags: list[str] = field(default_factory=list)

    def to_discover_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": _round_or_none(self.price, 8),
            "24h_change": _round_or_none(self.change_24h, 4),
            "volume_24h": _round_or_none(self.volume_24h, 2),
            "tags": self.tags,
        }

    def to_full_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["change_24h"] = _round_or_none(self.change_24h, 4)
        payload["volume_24h"] = _round_or_none(self.volume_24h, 2)
        payload["liquidity"] = _round_or_none(self.liquidity, 2)
        payload["market_cap"] = _round_or_none(self.market_cap, 2)
        payload["fdv"] = _round_or_none(self.fdv, 2)
        payload["price"] = _round_or_none(self.price, 8)
        return payload
