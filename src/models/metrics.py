"""Models for LLM execution metrics and baseline results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMMetrics(BaseModel):
    """Metrics captured from a single LLM invocation."""

    provider: str = Field(..., description="LLM provider: 'openai', 'anthropic', or 'ollama'.")
    model: str = Field(..., description="Model identifier, e.g. 'gpt-4o'.")
    input_tokens: int = Field(..., description="Number of input tokens consumed.")
    output_tokens: int = Field(..., description="Number of output tokens generated.")
    total_tokens: int = Field(..., description="Total tokens (input + output).")
    execution_time_seconds: float = Field(..., description="Wall-clock time for the LLM call.")
    estimated_cost_usd: float = Field(
        ..., description="Estimated cost in USD. 0.0 for local models."
    )


class BaselineResult(BaseModel):
    """Complete result from the single-agent baseline analysis."""

    markdown_content: str
    metrics: LLMMetrics
