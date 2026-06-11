from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import auth
import main
import session_manager as session_module


class FakeCursor:
    def __init__(self, *, fetchone_value=None, fetchall_value=None):
        self.fetchone_value = fetchone_value
        self.fetchall_value = fetchall_value or []
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.fetchone_value

    def fetchall(self):
        return self.fetchall_value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self.cursor_obj = cursor
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_session_lookup_returns_none_for_unknown_token(monkeypatch):
    cursor = FakeCursor(fetchone_value=None)
    monkeypatch.setattr(session_module, "get_connection", lambda: FakeConnection(cursor))

    manager = session_module.SessionManager()
    assert manager.get("missing-token") is None


def test_session_lookup_returns_none_for_revoked_session(monkeypatch):
    now = datetime.now(timezone.utc)
    cursor = FakeCursor(
        fetchone_value={
            "id": "sess-1",
            "user_id": "user-1",
            "email": "user@example.com",
            "role": "user",
            "is_active": True,
            "created_at": now,
            "expires_at": now + timedelta(hours=1),
            "revoked_at": now,
        }
    )
    monkeypatch.setattr(session_module, "get_connection", lambda: FakeConnection(cursor))

    manager = session_module.SessionManager()
    assert manager.get("revoked-token") is None


def test_session_lookup_returns_none_for_expired_session(monkeypatch):
    now = datetime.now(timezone.utc)
    cursor = FakeCursor(
        fetchone_value={
            "id": "sess-1",
            "user_id": "user-1",
            "email": "user@example.com",
            "role": "user",
            "is_active": True,
            "created_at": now - timedelta(hours=2),
            "expires_at": now - timedelta(minutes=1),
            "revoked_at": None,
        }
    )
    monkeypatch.setattr(session_module, "get_connection", lambda: FakeConnection(cursor))

    manager = session_module.SessionManager()
    assert manager.get("expired-token") is None


def test_session_lookup_returns_active_session_and_updates_last_seen(monkeypatch):
    now = datetime.now(timezone.utc)
    cursor = FakeCursor(
        fetchone_value={
            "id": "sess-1",
            "user_id": "user-1",
            "email": "user@example.com",
            "role": "admin",
            "is_active": True,
            "created_at": now - timedelta(minutes=10),
            "expires_at": now + timedelta(hours=1),
            "revoked_at": None,
        }
    )
    monkeypatch.setattr(session_module, "get_connection", lambda: FakeConnection(cursor))

    manager = session_module.SessionManager()
    session = manager.get("active-token")

    assert session is not None
    assert session["user_id"] == "user-1"
    assert session["email"] == "user@example.com"
    assert session["role"] == "admin"
    assert any("UPDATE auth_sessions SET last_seen_at" in query for query, _ in cursor.executed)


def test_rate_limit_below_threshold():
    now = datetime.now(timezone.utc)
    attempts = [(now - timedelta(minutes=1)).isoformat()] * 4
    limited, retry_after = auth.is_rate_limited(attempts, now=now)
    assert limited is False
    assert retry_after == 0


def test_rate_limit_at_threshold():
    now = datetime.now(timezone.utc)
    attempts = [(now - timedelta(minutes=1)).isoformat()] * 5
    limited, retry_after = auth.is_rate_limited(attempts, now=now)
    assert limited is True
    assert retry_after > 0


def test_rate_limit_ignores_expired_window():
    now = datetime.now(timezone.utc)
    attempts = [(now - timedelta(minutes=10)).isoformat()] * 6
    limited, retry_after = auth.is_rate_limited(attempts, now=now)
    assert limited is False
    assert retry_after == 0


def test_authenticate_user_returns_429_when_rate_limited(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(auth, "get_recent_failed_attempts", lambda email_attempt: [now] * 5)
    calls = []
    monkeypatch.setattr(auth, "record_login_attempt", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = auth.authenticate_user("User@example.com", "password1")

    assert result.ok is False
    assert result.status_code == 429
    assert "Too many failed login attempts" in result.message
    assert calls


def test_login_endpoint_returns_429_when_rate_limited(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(main, "init_database", lambda: None)
    monkeypatch.setattr(auth, "get_recent_failed_attempts", lambda email_attempt: [now] * 5)
    monkeypatch.setattr(auth, "record_login_attempt", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password1"},
        )

    assert response.status_code == 429
    assert "Too many failed login attempts" in response.json()["detail"]


class StubSessionManager:
    def __init__(self, session):
        self.session = session

    def get(self, token: str):
        return self.session


def test_auth_me_returns_user_for_valid_session(monkeypatch):
    monkeypatch.setattr(main, "init_database", lambda: None)
    monkeypatch.setattr(
        main,
        "session_manager",
        StubSessionManager(
            {
                "user_id": "user-1",
                "email": "user@example.com",
                "role": "user",
                "expires_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
    )

    with TestClient(main.app) as client:
        response = client.post("/api/auth/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_auth_me_rejects_expired_session(monkeypatch):
    monkeypatch.setattr(main, "init_database", lambda: None)
    monkeypatch.setattr(main, "session_manager", StubSessionManager(None))

    with TestClient(main.app) as client:
        response = client.post("/api/auth/me", headers={"Authorization": "Bearer expired-token"})

    assert response.status_code == 401


def test_auth_me_rejects_revoked_session(monkeypatch):
    monkeypatch.setattr(main, "init_database", lambda: None)
    monkeypatch.setattr(main, "session_manager", StubSessionManager(None))

    with TestClient(main.app) as client:
        response = client.post("/api/auth/me", headers={"Authorization": "Bearer revoked-token"})

    assert response.status_code == 401


def test_auth_me_rejects_unknown_session(monkeypatch):
    monkeypatch.setattr(main, "init_database", lambda: None)
    monkeypatch.setattr(main, "session_manager", StubSessionManager(None))

    with TestClient(main.app) as client:
        response = client.post("/api/auth/me", headers={"Authorization": "Bearer unknown-token"})

    assert response.status_code == 401


def test_chat_returns_pending_memory_for_remember_fact_tool(monkeypatch):
    monkeypatch.setattr(main, "init_database", lambda: None)
    monkeypatch.setattr(
        main,
        "session_manager",
        StubSessionManager(
            {
                "user_id": "user-1",
                "email": "user@example.com",
                "role": "user",
                "expires_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
    )
    monkeypatch.setattr(main, "check_message", lambda message: (False, None))
    monkeypatch.setattr(main, "load_user_profile", lambda user_id: {})
    monkeypatch.setattr(main, "_get_agent", lambda model_name, user_id: object())
    monkeypatch.setattr(
        main,
        "run_agent_tracked",
        lambda agent_executor, payload, model, config=None: (
            {
                "output": "I'll remember that preference.",
                "intermediate_steps": [
                    (
                        SimpleNamespace(
                            tool="remember_fact",
                            tool_input={"fact": "User prefers grilled fish over red meat"},
                        ),
                        "📝 Queued for confirmation: 'User prefers grilled fish over red meat'",
                    )
                ],
            },
            SimpleNamespace(total_tokens=42, estimated_cost_usd=0.001),
        ),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/chat",
            headers={"Authorization": "Bearer valid-token"},
            json={
                "message": "I prefer grilled fish over red meat.",
                "model": "claude-haiku-4-5",
                "chat_history": [],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["pending_memories"] == ["User prefers grilled fish over red meat"]
