"""
offers/ingest.py — refresh the cached supermarket offers.

Run after cloning and on a weekly schedule (offers rotate weekly):
    python offers/ingest.py

Runs every configured provider and replaces the `supermarket_offers` table with
the combined result. Mirrors the RAG ingest pattern in rag/ingest.py.
"""

from __future__ import annotations

from loguru import logger

from db import replace_offers
from offers.providers import OfferProvider, default_providers


def ingest(providers: list[OfferProvider] | None = None) -> int:
    """Fetch from all providers and replace the offers cache. Returns row count."""
    providers = providers or default_providers()

    rows: list[dict] = []
    for provider in providers:
        try:
            offers = provider.fetch()
        except Exception:
            logger.exception("Provider {} failed; skipping", provider.store)
            continue
        logger.info("{}: {} offers", provider.store, len(offers))
        rows.extend(offer.to_row() for offer in offers)

    count = replace_offers(rows)
    logger.info("Offers ingest complete — {} offers cached", count)
    return count


if __name__ == "__main__":
    ingest()
