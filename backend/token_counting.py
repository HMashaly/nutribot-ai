"""
token_counting.py — Token counting and cost estimation for NutriBot.
"""

from __future__ import annotations
from dataclasses import dataclass

COST_PER_1K: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":  {"input": 0.001, "output": 0.005},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
}
_FALLBACK_RATES = COST_PER_1K["claude-haiku-4-5"]


def count_tokens(text: str, model: str = "claude-haiku-4-5") -> int:
    # Anthropic models don't use tiktoken — fall back to a pure-Python estimate.
    return max(1, len(text) // 4)


def estimate_cost(tokens: int, model: str = "claude-haiku-4-5") -> float:
    rates = COST_PER_1K.get(model, _FALLBACK_RATES)
    half = tokens / 2
    return round((half / 1000) * rates["input"] + (half / 1000) * rates["output"], 6)


@dataclass
class TokenUsage:
    input_tokens: int         = 0
    output_tokens: int        = 0
    total_tokens: int         = 0
    model: str                = "claude-haiku-4-5"
    estimated_cost_usd: float = 0.0
    is_exact: bool            = False


def run_agent_tracked(
    agent_executor,
    payload: dict,
    model: str,
    config: dict | None = None,
) -> tuple[dict, TokenUsage]:
    """Invoke agent and capture real token usage via LangChain's provider-agnostic
    usage metadata callback (works with Claude's `AIMessage.usage_metadata`).

    `config` is forwarded to the agent (run name / tags / metadata) so traces in
    LangSmith carry the request's correlation ID, user, and model.
    """
    from langchain_core.callbacks.usage import get_usage_metadata_callback

    with get_usage_metadata_callback() as cb:
        result = agent_executor.invoke(payload, config=config)

    input_tok  = sum(usage.get("input_tokens", 0) for usage in cb.usage_metadata.values())
    output_tok = sum(usage.get("output_tokens", 0) for usage in cb.usage_metadata.values())
    total_tok  = sum(usage.get("total_tokens", 0) for usage in cb.usage_metadata.values())

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
