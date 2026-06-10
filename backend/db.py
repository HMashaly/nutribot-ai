"""
db.py — PostgreSQL helpers for NutriBot.
Pure Python — no Streamlit imports.
Reads the configured database URL from typed settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from config import settings


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection() -> psycopg.Connection:
    database_url = settings.effective_database_url
    if not database_url:
        raise RuntimeError("Database configuration is missing.")
    return psycopg.connect(database_url, row_factory=dict_row)


def init_database() -> None:
    """Run sql/schema.sql — idempotent (uses IF NOT EXISTS everywhere)."""
    schema_path = Path(__file__).resolve().parent / "sql" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


# ── Long-term memories (HITL-confirmed facts) ──────────────────────────────────

def get_memories(user_id: str) -> list[str]:
    """Load all stored memories for a user (oldest first)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT memory
                FROM user_memories
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return [row["memory"] for row in rows]


def save_memory(user_id: str, memory: str) -> None:
    """Persist one HITL-confirmed memory fact."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_memories (user_id, memory) VALUES (%s, %s)",
                (user_id, memory),
            )
        conn.commit()


# ── Supermarket offers ─────────────────────────────────────────────────────────

def get_offers_for_terms(terms: list[str]) -> list[dict[str, Any]]:
    """Return currently-valid offers whose normalized name matches any term.

    Matching is a case-insensitive substring (ILIKE) in either direction, so the
    ingredient "egg" matches a "free-range eggs" offer and vice versa. Offers
    whose validity window has already passed are excluded.
    """
    if not terms:
        return []

    clauses = " OR ".join(
        "(normalized_name ILIKE %s OR %s ILIKE '%%' || normalized_name || '%%')"
        for _ in terms
    )
    params: list[Any] = []
    for term in terms:
        params.extend([f"%{term}%", term])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT store, product_name, normalized_name, price_eur, unit,
                       discount_pct, valid_from, valid_to, source
                FROM   supermarket_offers
                WHERE  (valid_to IS NULL OR valid_to >= CURRENT_DATE)
                  AND  ({clauses})
                ORDER BY price_eur ASC NULLS LAST
                """,
                params,
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def has_fresh_offers() -> bool:
    """True if the offers cache has at least one currently-valid row."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM supermarket_offers "
                "WHERE valid_to IS NULL OR valid_to >= CURRENT_DATE LIMIT 1"
            )
            return cur.fetchone() is not None


def replace_offers(offers: list[dict[str, Any]]) -> int:
    """Refresh the offers cache: clear the table and insert the given offers.

    Called by offers/ingest.py. Returns the number of rows inserted.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM supermarket_offers")
            for offer in offers:
                cur.execute(
                    """
                    INSERT INTO supermarket_offers
                        (store, product_name, normalized_name, price_eur, unit,
                         discount_pct, valid_from, valid_to, source)
                    VALUES
                        (%(store)s, %(product_name)s, %(normalized_name)s, %(price_eur)s,
                         %(unit)s, %(discount_pct)s, %(valid_from)s, %(valid_to)s, %(source)s)
                    """,
                    offer,
                )
        conn.commit()
    return len(offers)


# ── Sidebar profile ────────────────────────────────────────────────────────────

def load_user_profile(user_id: str) -> dict[str, Any]:
    """
    Return the user's saved profile as a plain dict.
    Returns an empty dict when no profile has been saved yet.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT weight_kg, height_cm, age, gender,
                       activity_level, goal, dietary_restrictions, updated_at
                FROM   user_profiles
                WHERE  user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else {}


def save_user_profile(user_id: str, profile: dict[str, Any]) -> None:
    """Upsert the user's profile. Missing keys are left as-is in the DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles
                    (user_id, weight_kg, height_cm, age, gender,
                     activity_level, goal, dietary_restrictions, updated_at)
                VALUES
                    (%(user_id)s, %(weight_kg)s, %(height_cm)s, %(age)s, %(gender)s,
                     %(activity_level)s, %(goal)s, %(dietary_restrictions)s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    weight_kg            = COALESCE(EXCLUDED.weight_kg,            user_profiles.weight_kg),
                    height_cm            = COALESCE(EXCLUDED.height_cm,            user_profiles.height_cm),
                    age                  = COALESCE(EXCLUDED.age,                  user_profiles.age),
                    gender               = COALESCE(EXCLUDED.gender,               user_profiles.gender),
                    activity_level       = COALESCE(EXCLUDED.activity_level,       user_profiles.activity_level),
                    goal                 = COALESCE(EXCLUDED.goal,                 user_profiles.goal),
                    dietary_restrictions = COALESCE(EXCLUDED.dietary_restrictions, user_profiles.dietary_restrictions),
                    updated_at           = NOW()
                """,
                {
                    "user_id":              user_id,
                    "weight_kg":            profile.get("weight_kg"),
                    "height_cm":            profile.get("height_cm"),
                    "age":                  profile.get("age"),
                    "gender":               profile.get("gender"),
                    "activity_level":       profile.get("activity_level"),
                    "goal":                 profile.get("goal"),
                    "dietary_restrictions": profile.get("dietary_restrictions"),
                },
            )
        conn.commit()
