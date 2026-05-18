"""
session_manager.py — In-memory token-based session store (8h TTL).
For production scale, swap the dict for Redis.
"""
from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone

SESSION_TTL_HOURS = 8

class SessionManager:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create(self, user_id: str, email: str, role: str = "user") -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = {
            "user_id": user_id, "email": email, "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
        }
        return token

    def get(self, token: str) -> dict | None:
        session = self._sessions.get(token)
        if not session:
            return None
        if datetime.now(timezone.utc) > datetime.fromisoformat(session["expires_at"]):
            del self._sessions[token]
            return None
        return session

    def delete(self, token: str) -> None:
        self._sessions.pop(token, None)
