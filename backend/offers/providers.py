"""
offers/providers.py — pluggable sources of supermarket offers.

Each provider returns a list of `Offer`s for one German chain. They all share a
seeded sample dataset (`seed_offers.json`) so the feature always demos with real
chain names. `AldiOfferProvider` additionally attempts a live fetch and falls
back to seed on any failure — that is the seam where a real per-chain scraper
gets wired in, without the agent, API, or UI needing to change.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from offers.matcher import normalize

SEED_PATH = Path(__file__).parent / "seed_offers.json"
DEFAULT_VALID_DAYS = 7


@dataclass
class Offer:
    store: str
    product_name: str
    normalized_name: str
    price_eur: float | None
    unit: str | None
    discount_pct: float | None
    valid_from: str  # ISO date
    valid_to: str    # ISO date
    source: str = "seed"

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _load_seed() -> list[dict[str, Any]]:
    if not SEED_PATH.exists():
        logger.warning("Seed offers file missing: {}", SEED_PATH)
        return []
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _seed_offers(
    source: str = "seed",
    stores: Iterable[str] | None = None,
    valid_days: int = DEFAULT_VALID_DAYS,
) -> list[Offer]:
    """Build Offers from the seed file, validity anchored to today."""
    today = date.today()
    valid_to = (today + timedelta(days=valid_days)).isoformat()
    store_filter = set(stores) if stores else None

    offers: list[Offer] = []
    for row in _load_seed():
        if store_filter and row["store"] not in store_filter:
            continue
        offers.append(Offer(
            store=row["store"],
            product_name=row["product_name"],
            normalized_name=normalize(row.get("normalized_name") or row["product_name"]),
            price_eur=row.get("price_eur"),
            unit=row.get("unit"),
            discount_pct=row.get("discount_pct"),
            valid_from=today.isoformat(),
            valid_to=valid_to,
            source=source,
        ))
    return offers


class OfferProvider(ABC):
    """A source of offers for one chain (or '*' for the whole seed set)."""

    store: str

    @abstractmethod
    def fetch(self) -> list[Offer]:
        ...


class SeedOfferProvider(OfferProvider):
    """Every seeded offer across all chains (used for simple/local runs)."""

    store = "*"

    def fetch(self) -> list[Offer]:
        return _seed_offers(source="seed")


class _SeedStoreProvider(OfferProvider):
    """Seed-only provider scoped to a single chain."""

    def __init__(self, store: str):
        self.store = store

    def fetch(self) -> list[Offer]:
        return _seed_offers(source="seed", stores={self.store})


class AldiOfferProvider(OfferProvider):
    """Best-effort live Aldi Süd offers; falls back to the seeded Aldi rows."""

    store = "Aldi Süd"

    def fetch(self) -> list[Offer]:
        try:
            live = self._fetch_live()
            if live:
                logger.info("Aldi live fetch returned {} offers", len(live))
                return live
        except Exception as exc:  # network, parsing, schema drift — never crash ingest
            logger.warning("Aldi live fetch failed ({}); using seed", exc)
        return _seed_offers(source="seed", stores={self.store})

    def _fetch_live(self) -> list[Offer]:
        # Seam for the real Aldi Süd offers endpoint. Returns nothing today so we
        # fall back to seed; implement the HTTP request + parse here to go live.
        return []


def default_providers() -> list[OfferProvider]:
    """One provider per named chain — swap any to a live scraper later."""
    return [
        AldiOfferProvider(),
        _SeedStoreProvider("Lidl"),
        _SeedStoreProvider("Rewe"),
        _SeedStoreProvider("Norma"),
        _SeedStoreProvider("Netto"),
    ]
