"""LLM provider factory — returns the configured LLM client.

Supports OpenAI, Anthropic, and Ollama (local) based on settings.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from src.config import LLMProvider, settings


def get_llm() -> BaseChatModel:
    """Return a LangChain chat model based on the active LLM provider."""
    match settings.llm_provider:
        case LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
            )
        case LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=settings.anthropic_model,
                api_key=settings.anthropic_api_key,
            )
        case LLMProvider.OLLAMA:
            from langchain_community.chat_models import ChatOllama

            return ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
