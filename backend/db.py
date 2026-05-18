"""
db.py — PostgreSQL helpers for NutriBot.
Pure Python — no Streamlit imports.
Reads DATABASE_URL from environment (set via .env or deployment platform).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import psycopg
from psycopg.rows import dict_row


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url, row_factory=dict_row)

    def _req(name: str) -> str:
        v = os.getenv(name)
        if not v:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return v

    return psycopg.connect(
        host=_req("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=_req("POSTGRES_DB"),
        user=_req("POSTGRES_USER"),
        password=_req("POSTGRES_PASSWORD"),
        row_factory=dict_row,
    )


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
