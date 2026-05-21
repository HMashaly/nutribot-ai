"""
session_manager.py — PostgreSQL-backed token session store.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from db import get_connection


class SessionManager:
    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(
        self,
        user_id: str,
        email: str,
        role: str = "user",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.session_max_hours)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_sessions (
                        user_id, token_hash, ip_address, user_agent,
                        created_at, expires_at, last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, token_hash, ip_address, user_agent, now, expires_at, now),
                )
            conn.commit()

        return token

    def get(self, token: str) -> dict[str, Any] | None:
        token_hash = self._hash_token(token)
        now = datetime.now(timezone.utc)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.id, s.user_id, s.created_at, s.expires_at, s.revoked_at,
                           u.email, u.role, u.is_active
                    FROM auth_sessions s
                    JOIN users u ON u.id = s.user_id
                    WHERE s.token_hash = %s
                    """,
                    (token_hash,),
                )
                session = cur.fetchone()

                if not session:
                    return None

                if session["revoked_at"] is not None or not session["is_active"]:
                    return None

                expires_at = session["expires_at"]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    return None

                cur.execute(
                    "UPDATE auth_sessions SET last_seen_at = %s WHERE id = %s",
                    (now, session["id"]),
                )
            conn.commit()

        return {
            "user_id": str(session["user_id"]),
            "email": session["email"],
            "role": session["role"],
            "created_at": session["created_at"].isoformat(),
            "expires_at": session["expires_at"].isoformat(),
        }

    def delete(self, token: str) -> None:
        token_hash = self._hash_token(token)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = NOW()
                    WHERE token_hash = %s AND revoked_at IS NULL
                    """,
                    (token_hash,),
                )
            conn.commit()
