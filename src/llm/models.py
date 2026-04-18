"""Model catalog and availability checks."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import Environment, settings


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for a single LLM model."""

    provider: str  # "openai" | "anthropic" | "ollama"
    model_id: str  # API model identifier
    label: str  # Display name for the frontend
    tier: str  # "economic" | "performance" | "local"
    supports_vision: bool


MODEL_CATALOG: list[ModelInfo] = [
    ModelInfo("openai", "gpt-4o-mini", "GPT-4o Mini", "economic", True),
    ModelInfo("openai", "gpt-5.2", "GPT-5.2", "performance", True),
    ModelInfo(
        "anthropic", "claude-haiku-4-5-20251001", "Claude Haiku 4.5", "economic", True
    ),
    ModelInfo("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", "performance", True),
    ModelInfo(
        "ollama",
        settings.ollama_model,
        f"{settings.ollama_model} (Local)",
        "local",
        False,
    ),
]


def get_available_models() -> list[ModelInfo]:
    """Return models available given current environment and API keys."""
    available: list[ModelInfo] = []
    for m in MODEL_CATALOG:
        if m.provider == "ollama":
            if settings.environment == Environment.LOCAL:
                available.append(m)
        elif m.provider == "openai":
            if settings.openai_api_key:
                available.append(m)
        elif m.provider == "anthropic":
            if settings.anthropic_api_key:
                available.append(m)
    return available
