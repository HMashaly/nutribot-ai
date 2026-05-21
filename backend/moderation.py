"""
moderation.py — Mistral content moderation wrapper.
Fails open: if Mistral is unavailable, message passes through.
"""

try:
    from mistralai import Mistral
except Exception:
    Mistral = None  # type: ignore[assignment]

from config import settings

MODERATION_POLICY = {
    "jailbreak": 0.7,
    "violence_and_threats": 0.7,
    "self_harm": 0.7,
    "criminal_content": 0.7,
    "hate_and_discrimination": 0.7,
}


def check_message(user_message: str) -> tuple[bool, str]:
    """
    Moderate user input with Mistral moderation API.
    Returns (blocked: bool, reason: str).
    Fails open on errors or missing API key.
    """
    if Mistral is None:
        return False, ""

    if not settings.mistral_api_key:
        return False, ""

    try:
        client = Mistral(api_key=settings.mistral_api_key)
        response = client.classifiers.moderate(
            model=settings.moderation_model,
            inputs=[{"role": "user", "content": user_message}],
        )
        result = response.results[0]
        for category, score in result.category_scores.items():
            threshold = MODERATION_POLICY.get(category)
            if threshold is not None and score > threshold:
                return True, category
        return False, ""
    except Exception:
        return False, ""
