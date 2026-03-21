"""LLM provider factory — returns the configured LLM client.

Supports OpenAI, Anthropic, and Ollama (local).
Accepts per-request provider/model overrides.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from src.config import LLMProvider, settings


def get_llm(
    provider: str | None = None,
    model: str | None = None,
) -> BaseChatModel:
    """Return a LangChain chat model.

    If ``provider`` and ``model`` are given, they override the global settings.
    Otherwise falls back to ``settings.llm_provider`` / model.
    """
    resolved_provider = provider or settings.llm_provider.value
    resolved_model = model

    match resolved_provider:
        case "openai" | LLMProvider.OPENAI:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set")
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=resolved_model or settings.openai_model,
                api_key=settings.openai_api_key,
            )
        case "anthropic" | LLMProvider.ANTHROPIC:
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set")
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=resolved_model or settings.anthropic_model,
                api_key=settings.anthropic_api_key,
            )
        case "ollama" | LLMProvider.OLLAMA:
            from langchain_community.chat_models import ChatOllama

            return ChatOllama(
                model=resolved_model or settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {resolved_provider}")
