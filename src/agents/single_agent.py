"""Single Agent (Baseline): generates a complete architecture report in one LLM call."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.base import BaseAgent
from src.llm.prompts import SINGLE_AGENT_SYSTEM_PROMPT, format_user_message
from src.llm.providers import get_llm

logger = structlog.get_logger()


class SingleAgent(BaseAgent):
    """Baseline agent that produces a full architecture report in a single LLM call.

    The LLM generates a Markdown document directly. All providers use the same
    plain ainvoke() path — no structured output or JSON schema injection.
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._llm = llm or get_llm(provider=provider, model=model)

    @property
    def name(self) -> str:
        return "SingleAgent"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the single-agent analysis pipeline."""
        project_description = state["project_description"]
        documents = state.get("user_documents", [])
        images = state.get("user_images", [])

        content = format_user_message(project_description, documents, images)

        logger.info(
            "Starting single-agent analysis",
            provider=self._provider,
            model=self._model,
        )

        raw_text, metrics = await self._invoke_and_measure(
            SINGLE_AGENT_SYSTEM_PROMPT, content
        )
        markdown = self._extract_markdown(raw_text)

        logger.info(
            "Single-agent analysis complete",
            execution_time=f"{metrics['execution_time_seconds']:.2f}s",
            total_tokens=metrics["total_tokens"],
            cost=f"${metrics['estimated_cost_usd']:.4f}",
        )

        return {
            "markdown_content": markdown,
            "metrics": metrics,
        }

    def _extract_markdown(self, content: str) -> str:
        """Strip accidental code-block wrappers from LLM output.

        Some models (especially Ollama) wrap the entire response in
        ```markdown ... ``` or ``` ... ``` despite being told not to.
        Uses rfind for the closing fence to preserve internal Mermaid fences.
        """
        content = content.strip()

        if content.startswith("```markdown"):
            inner = content[len("```markdown"):]
            if "```" in inner:
                inner = inner[:inner.rfind("```")]
            return inner.strip()

        if content.startswith("```") and content.endswith("```") and content.count("```") == 2:
            inner = content[3:content.rfind("```")]
            return inner.strip()

        return content
