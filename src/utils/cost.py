"""Cost estimation for LLM API calls.

Prices last verified: 2026-03.
"""

from __future__ import annotations

# (provider, model) -> (input_price_per_1k_tokens, output_price_per_1k_tokens)
COST_PER_1K_TOKENS: dict[tuple[str, str], tuple[float, float]] = {
    # OpenAI
    ("openai", "gpt-4o-mini"): (0.00015, 0.0006),  # $0.15/1M in, $0.60/1M out
    ("openai", "gpt-5.2"): (0.00175, 0.014),  # $1.75/1M in, $14.00/1M out
    # Anthropic
    ("anthropic", "claude-haiku-4-5-20251001"): (0.001, 0.005),  # $1/MTok in, $5/MTok out
    ("anthropic", "claude-sonnet-4-6"): (0.003, 0.015),  # $3/MTok in, $15/MTok out
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
