"""
offers/matcher.py — match recipe ingredients to cached supermarket offers.

The core (`normalize`, `expand_terms`, `match_offers`) is pure Python: the
database read is injected via the `fetch` argument, so the matching logic can be
unit-tested without a database. `match_offers` defaults to the real DB read when
`fetch` is not supplied.

Ingredient names are normalised and expanded with a small English↔German synonym
map (egg→Ei, milk→Milch, …) so an English recipe still matches German offers.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

# Each group is a set of interchangeable terms across English and German.
SYNONYM_GROUPS: list[set[str]] = [
    {"egg", "eggs", "ei", "eier"},
    {"milk", "milch"},
    {"butter"},
    {"onion", "onions", "zwiebel", "zwiebeln"},
    {"flour", "mehl"},
    {"cheese", "kaese", "käse"},
    {"chicken", "haehnchen", "hähnchen", "huhn"},
    {"tomato", "tomatoes", "tomate", "tomaten"},
    {"oil", "oel", "öl"},
    {"rice", "reis"},
    {"potato", "potatoes", "kartoffel", "kartoffeln"},
    {"sugar", "zucker"},
    {"salt", "salz"},
    {"bread", "brot"},
    {"yogurt", "yoghurt", "joghurt"},
    {"apple", "apples", "apfel", "aepfel", "äpfel"},
    {"banana", "bananas", "banane", "bananen"},
    {"pasta", "noodles", "nudeln", "spaghetti"},
    {"beef", "rind", "rindfleisch"},
    {"pork", "schwein", "schweinefleisch"},
    {"fish", "fisch"},
    {"carrot", "carrots", "karotte", "karotten", "moehre", "möhre"},
    {"pepper", "paprika"},
    {"garlic", "knoblauch"},
    {"spinach", "spinat"},
    {"cream", "sahne"},
]

# token -> every synonym in its group (including itself)
_SYNONYM_INDEX: dict[str, set[str]] = {}
for _group in SYNONYM_GROUPS:
    for _term in _group:
        _SYNONYM_INDEX.setdefault(_term, set()).update(_group)


def normalize(name: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace. Keeps umlauts."""
    lowered = (name or "").lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokens(name: str) -> set[str]:
    return {t for t in normalize(name).split() if t}


def expand_terms(ingredient: str) -> set[str]:
    """Normalised tokens of an ingredient, plus their known synonyms."""
    terms: set[str] = set()
    for token in _tokens(ingredient):
        terms.add(token)
        terms.update(_SYNONYM_INDEX.get(token, set()))
    return terms


def _offer_matches(offer_tokens: set[str], terms: set[str]) -> int:
    """Score how well an offer matches a term set (0 = no match).

    Whole-token overlap is the primary signal. The substring fallback is kept
    deliberately conservative — only terms of 4+ chars, and only when the term
    appears inside an offer token — so a short token like "ei" (German for egg)
    can't spuriously match inside "weizenmehl" (flour).
    """
    direct = offer_tokens & terms
    if direct:
        return len(direct) + 1
    for term in terms:
        if len(term) >= 4 and any(term in tok for tok in offer_tokens):
            return 1
    return 0


def _best_per_store(matches: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Keep the cheapest offer per store, then sort cheapest-first."""
    by_store: dict[str, dict[str, Any]] = {}
    for offer in matches:
        store = offer["store"]
        price = offer.get("price_eur")
        current = by_store.get(store)
        if current is None or _price_key(price) < _price_key(current.get("price_eur")):
            by_store[store] = offer
    ranked = sorted(by_store.values(), key=lambda o: _price_key(o.get("price_eur")))
    return ranked[:limit]


def _price_key(price: Any) -> float:
    return float(price) if price is not None else float("inf")


def match_offers(
    ingredients: Iterable[str],
    fetch: Callable[[list[str]], list[dict[str, Any]]] | None = None,
    max_per_ingredient: int = 5,
) -> list[dict[str, Any]]:
    """Match each ingredient to current offers, cheapest per store.

    Returns a list of ``{"ingredient": str, "offers": [offer, ...]}`` — one entry
    per requested ingredient (with an empty list when nothing is on sale).
    """
    ingredient_list = [i.strip() for i in ingredients if i and i.strip()]
    if not ingredient_list:
        return []

    if fetch is None:
        from db import get_offers_for_terms as fetch  # lazy import avoids cycle

    # One DB round-trip for the union of all expanded terms.
    all_terms: set[str] = set()
    per_ingredient_terms: dict[str, set[str]] = {}
    for ingredient in ingredient_list:
        terms = expand_terms(ingredient)
        per_ingredient_terms[ingredient] = terms
        all_terms.update(terms)

    candidates = fetch(sorted(all_terms)) if all_terms else []

    results: list[dict[str, Any]] = []
    for ingredient in ingredient_list:
        terms = per_ingredient_terms[ingredient]
        scored: list[tuple[int, dict[str, Any]]] = []
        for offer in candidates:
            tokens = _tokens(offer.get("normalized_name") or offer.get("product_name", ""))
            score = _offer_matches(tokens, terms)
            if score:
                scored.append((score, offer))
        matches = [offer for _, offer in scored]
        results.append({
            "ingredient": ingredient,
            "offers": _best_per_store(matches, max_per_ingredient),
        })
    return results


def format_offers_text(matches: list[dict[str, Any]]) -> str:
    """Render match_offers output as a readable summary for the agent."""
    if not matches:
        return "No ingredients were provided to look up."

    lines: list[str] = ["🛒 Current German supermarket offers:"]
    any_found = False
    for entry in matches:
        ingredient = entry["ingredient"]
        offers = entry["offers"]
        if not offers:
            lines.append(f"\n• {ingredient}: no current offers found.")
            continue
        any_found = True
        lines.append(f"\n• {ingredient}:")
        for offer in offers:
            price = offer.get("price_eur")
            price_str = f"€{float(price):.2f}" if price is not None else "price n/a"
            unit = f" / {offer['unit']}" if offer.get("unit") else ""
            disc = offer.get("discount_pct")
            disc_str = f" (−{float(disc):.0f}%)" if disc else ""
            valid = f", until {offer['valid_to']}" if offer.get("valid_to") else ""
            lines.append(
                f"    - {offer['store']}: {offer['product_name']} "
                f"{price_str}{unit}{disc_str}{valid}"
            )

    if not any_found:
        lines.append("\n(No matching offers in the current cache.)")
    lines.append(
        "\n\nℹ️ Offers are cached weekly; Aldi data is fetched live where available, "
        "the rest are seeded samples. Always confirm prices in-store."
    )
    return "\n".join(lines)
