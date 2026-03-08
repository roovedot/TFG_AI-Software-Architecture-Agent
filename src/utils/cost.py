"""Cost estimation for LLM API calls.

Prices last verified: 2025-03.
"""

from __future__ import annotations

# (provider, model) -> (input_price_per_1k_tokens, output_price_per_1k_tokens)
COST_PER_1K_TOKENS: dict[tuple[str, str], tuple[float, float]] = {
    # OpenAI
    ("openai", "gpt-4o"): (0.0025, 0.010),
    ("openai", "gpt-4o-mini"): (0.00015, 0.0006),
    ("openai", "gpt-4.1"): (0.002, 0.008),
    ("openai", "gpt-4.1-mini"): (0.0004, 0.0016),
    ("openai", "gpt-4.1-nano"): (0.0001, 0.0004),
    # Anthropic
    ("anthropic", "claude-sonnet-4-20250514"): (0.003, 0.015),
    ("anthropic", "claude-opus-4-20250514"): (0.015, 0.075),
    ("anthropic", "claude-haiku-4-20250414"): (0.0008, 0.004),
    # Ollama (local, free)
    ("ollama", "*"): (0.0, 0.0),
}


def estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    """Estimate the cost of an LLM call in USD.

    Returns 0.0 for unknown models or local providers.
    """
    key = (provider, model)
    if key not in COST_PER_1K_TOKENS:
        # Try wildcard for the provider (e.g., ollama)
        key = (provider, "*")
    if key not in COST_PER_1K_TOKENS:
        return 0.0

    input_rate, output_rate = COST_PER_1K_TOKENS[key]
    return (input_tokens / 1000 * input_rate) + (output_tokens / 1000 * output_rate)
