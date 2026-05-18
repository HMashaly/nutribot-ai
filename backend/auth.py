"""
auth.py — Authentication and admin helpers for NutriBot.
No Streamlit imports — pure Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from email_validator import EmailNotValidError, validate_email
from passlib.context import CryptContext

from db import get_connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class AuthResult:
    ok: bool
    message: str
    user: dict = field(default_factory=dict)


# ── Email validation ───────────────────────────────────────────────────────────

def normalize_email(email: str) -> str:
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


# ── Password validation ────────────────────────────────────────────────────────

def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one number.")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


# ── User management ────────────────────────────────────────────────────────────

def create_user(email: str, password: str) -> AuthResult:
    try:
        normalized_email = normalize_email(email)
        validate_password_strength(password)
    except ValueError as exc:
        return AuthResult(ok=False, message=str(exc))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (normalized_email,))
            if cur.fetchone():
                return AuthResult(ok=False, message="An account with that email already exists.")

            cur.execute(
                """
                INSERT INTO users (email, password_hash)
                VALUES (%s, %s)
                RETURNING id, email, role, is_active, created_at
                """,
                (normalized_email, hash_password(password)),
            )
            user = cur.fetchone()
        conn.commit()

    return AuthResult(
        ok=True,
        message="Account created successfully. You can now sign in.",
        user=user,
    )


def authenticate_user(
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthResult:
    normalized_email = email.strip().lower()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, role, is_active, created_at
                FROM users
                WHERE email = %s
                """,
                (normalized_email,),
            )
            user = cur.fetchone()

    if not user:
        record_login_attempt(normalized_email, False, failure_reason="user_not_found",
                             ip_address=ip_address, user_agent=user_agent)
        return AuthResult(ok=False, message="Invalid credentials.")

    if not user["is_active"]:
        record_login_attempt(normalized_email, False, user_id=user["id"],
                             failure_reason="user_inactive", ip_address=ip_address)
        return AuthResult(ok=False, message="This account has been disabled.")

    if not verify_password(password, user["password_hash"]):
        record_login_attempt(normalized_email, False, user_id=user["id"],
                             failure_reason="bad_password", ip_address=ip_address)
        return AuthResult(ok=False, message="Invalid credentials.")

    safe_user = {
        "id":         user["id"],
        "email":      user["email"],
        "role":       user["role"],
        "is_active":  user["is_active"],
        "created_at": user["created_at"],
    }
    record_login_attempt(normalized_email, True, user_id=user["id"], ip_address=ip_address)
    return AuthResult(ok=True, message="Signed in successfully.", user=safe_user)


def record_login_attempt(
    email_attempt: str,
    success: bool,
    user_id: str | None = None,
    failure_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO login_audit (
                    user_id, email_attempt, success, ip_address, user_agent, failure_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, email_attempt, success, ip_address, user_agent, failure_reason),
            )
        conn.commit()


def get_admin_dashboard_stats() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM users")
            total_users = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
            total_admins = cur.fetchone()["count"]

            cur.execute(
                """
                SELECT email_attempt, success, failure_reason, created_at
                FROM login_audit
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            recent_logins = cur.fetchall()

    return {
        "total_users":   total_users,
        "total_admins":  total_admins,
        "recent_logins": recent_logins,
    }


def is_rate_limited(failed_attempts: list[str], now: datetime | None = None) -> tuple[bool, int]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=5)
    recent = [t for t in failed_attempts if datetime.fromisoformat(t) >= cutoff]
    if len(recent) >= 5:
        oldest = datetime.fromisoformat(recent[0]) + timedelta(minutes=5)
        remaining = max(1, int((oldest - now).total_seconds()))
        return True, remaining
    return False, 0
