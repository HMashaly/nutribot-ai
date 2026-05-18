"""
moderation.py — Mistral content moderation wrapper.
Fails open: if Mistral is unavailable, message passes through.
"""

import os

try:
    from mistralai import Mistral
except Exception:
    Mistral = None  # type: ignore[assignment]

BLOCKED_CATEGORIES = {"jailbreak", "violence_and_threats"}


def check_message(user_message: str) -> tuple[bool, str]:
    """
    Moderate user input with Mistral moderation API.
    Returns (blocked: bool, reason: str).
    Fails open on errors or missing API key.
    """
    if Mistral is None:
        return False, ""

    api_key = os.getenv("MISTRAL_API_KEY", "")
    if not api_key:
        return False, ""

    try:
        client = Mistral(api_key=api_key)
        response = client.classifiers.moderate(
            model="mistral-moderation-2411",
            inputs=[{"role": "user", "content": user_message}],
        )
        result = response.results[0]
        for category, score in result.category_scores.items():
            if category in BLOCKED_CATEGORIES and score > 0.7:
                return True, category
        return False, ""
    except Exception:
        return False, ""
