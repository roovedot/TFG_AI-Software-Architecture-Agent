"""Application configuration with support for dev/prod environments.

Usage:
    from src.config import settings
    print(settings.llm_provider)  # "ollama" in dev, "openai" in prod
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class EmbeddingProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    environment: Environment = Environment.DEVELOPMENT

    # LLM
    llm_provider: LLMProvider = LLMProvider.OLLAMA

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Embeddings
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OPENAI
    embedding_model: str = "text-embedding-3-small"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "knowledge_base"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    log_level: str = "debug"

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "tfg-multiagent-architect"

    @property
    def is_dev(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_prod(self) -> bool:
        return self.environment == Environment.PRODUCTION


settings = Settings()
