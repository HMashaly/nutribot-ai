"""
token_counting.py — Token counting and cost estimation for NutriBot.
"""

from __future__ import annotations
from dataclasses import dataclass

COST_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o":      {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}
_FALLBACK_RATES = COST_PER_1K["gpt-4o-mini"]


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def estimate_cost(tokens: int, model: str = "gpt-4o-mini") -> float:
    rates = COST_PER_1K.get(model, _FALLBACK_RATES)
    half = tokens / 2
    return round((half / 1000) * rates["input"] + (half / 1000) * rates["output"], 6)


@dataclass
class TokenUsage:
    input_tokens: int         = 0
    output_tokens: int        = 0
    total_tokens: int         = 0
    model: str                = "gpt-4o-mini"
    estimated_cost_usd: float = 0.0
    is_exact: bool            = False


def run_agent_tracked(agent_executor, payload: dict, model: str) -> tuple[dict, TokenUsage]:
    """Invoke agent and capture real token usage via LangChain OpenAI callback."""
    from langchain_community.callbacks.manager import get_openai_callback

    with get_openai_callback() as cb:
        result = agent_executor.invoke(payload)

    input_tok  = cb.prompt_tokens
    output_tok = cb.completion_tokens
    total_tok  = cb.total_tokens

    if total_tok == 0:
        input_text  = str(payload.get("input", ""))
        output_text = result.get("output", "") if isinstance(result, dict) else ""
        input_tok   = count_tokens(input_text, model)
        output_tok  = count_tokens(output_text, model)
        total_tok   = input_tok + output_tok
        is_exact    = False
    else:
        is_exact = True

    rates = COST_PER_1K.get(model, _FALLBACK_RATES)
    cost  = round(
        (input_tok  / 1000) * rates["input"] +
        (output_tok / 1000) * rates["output"],
        6,
    )

    return result, TokenUsage(
        input_tokens=input_tok,
        output_tokens=output_tok,
        total_tokens=total_tok,
        model=model,
        estimated_cost_usd=cost,
        is_exact=is_exact,
    )
