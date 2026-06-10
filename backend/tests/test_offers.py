"""
tests/test_offers.py — unit tests for the offer matcher.

The matcher's DB read is injected, so these run without a database.
"""

from offers.matcher import (
    expand_terms,
    format_offers_text,
    match_offers,
    normalize,
)

# Fake "DB" rows; the fake fetch returns all of them regardless of terms, so the
# matcher's own scoring is what's under test.
FAKE_OFFERS = [
    {"store": "Aldi Süd", "product_name": "Eier 10er",     "normalized_name": "eier eggs",      "price_eur": 1.89, "unit": "10 pack", "discount_pct": 15, "valid_to": "2026-12-31"},
    {"store": "Aldi Süd", "product_name": "Bio Eier 6er",  "normalized_name": "eier eggs bio",  "price_eur": 2.49, "unit": "6 pack",  "discount_pct": None, "valid_to": "2026-12-31"},
    {"store": "Lidl",     "product_name": "Eier 10er",     "normalized_name": "eier eggs",      "price_eur": 1.49, "unit": "10 pack", "discount_pct": 10, "valid_to": "2026-12-31"},
    {"store": "Aldi Süd", "product_name": "Vollmilch 1L",  "normalized_name": "milch milk",     "price_eur": 0.95, "unit": "1 L",     "discount_pct": None, "valid_to": "2026-12-31"},
    {"store": "Rewe",     "product_name": "Bio Milch 1L",  "normalized_name": "milch milk bio", "price_eur": 1.29, "unit": "1 L",     "discount_pct": None, "valid_to": "2026-12-31"},
]


def _fetch(_terms):
    return list(FAKE_OFFERS)


class TestNormalize:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize("  Frische Eier! ") == "frische eier"

    def test_keeps_umlauts(self):
        assert normalize("Hähnchen") == "hähnchen"


class TestExpandTerms:
    def test_english_ingredient_expands_to_german(self):
        terms = expand_terms("egg")
        assert "ei" in terms and "eier" in terms and "eggs" in terms

    def test_unknown_term_returns_itself(self):
        assert expand_terms("quinoa") == {"quinoa"}


class TestMatchOffers:
    def test_synonym_match_english_to_german(self):
        result = match_offers(["egg"], fetch=_fetch)
        assert len(result) == 1
        assert result[0]["ingredient"] == "egg"
        stores = {o["store"] for o in result[0]["offers"]}
        assert stores == {"Aldi Süd", "Lidl"}

    def test_keeps_cheapest_per_store(self):
        # Aldi has eggs at 1.89 and 2.49 — only the cheaper one should survive.
        offers = match_offers(["egg"], fetch=_fetch)[0]["offers"]
        aldi = [o for o in offers if o["store"] == "Aldi Süd"]
        assert len(aldi) == 1
        assert float(aldi[0]["price_eur"]) == 1.89

    def test_sorted_cheapest_first(self):
        offers = match_offers(["egg"], fetch=_fetch)[0]["offers"]
        prices = [float(o["price_eur"]) for o in offers]
        assert prices == sorted(prices)
        assert offers[0]["store"] == "Lidl"  # 1.49 < 1.89

    def test_no_match_returns_empty_offers(self):
        result = match_offers(["chocolate"], fetch=_fetch)
        assert result[0]["ingredient"] == "chocolate"
        assert result[0]["offers"] == []

    def test_multiple_ingredients(self):
        result = match_offers(["egg", "milk"], fetch=_fetch)
        ingredients = [r["ingredient"] for r in result]
        assert ingredients == ["egg", "milk"]
        milk = next(r for r in result if r["ingredient"] == "milk")
        assert milk["offers"][0]["store"] == "Aldi Süd"  # 0.95 cheapest

    def test_empty_input(self):
        assert match_offers([], fetch=_fetch) == []


class TestFormatOffersText:
    def test_renders_store_and_price(self):
        text = format_offers_text(match_offers(["egg"], fetch=_fetch))
        assert "Lidl" in text and "€1.49" in text

    def test_no_offers_message(self):
        text = format_offers_text(match_offers(["chocolate"], fetch=_fetch))
        assert "no current offers" in text.lower()
