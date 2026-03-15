"""Single Agent (Baseline): generates a complete architecture report in one LLM call."""

from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.base import BaseAgent
from src.config import LLMProvider, settings
from src.llm.prompts import SINGLE_AGENT_SYSTEM_PROMPT, format_user_message
from src.llm.providers import get_llm
from src.utils.cost import estimate_cost

logger = structlog.get_logger()


class SingleAgent(BaseAgent):
    """Baseline agent that produces a full architecture report in a single LLM call.

    The LLM generates a Markdown document directly. All providers use the same
    plain ainvoke() path — no structured output or JSON schema injection.
    """

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        self._llm = llm or get_llm()

    @property
    def name(self) -> str:
        return "SingleAgent"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the single-agent analysis pipeline."""
        project_description = state["project_description"]
        documents = state.get("user_documents", [])

        messages = [
            SystemMessage(content=SINGLE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=format_user_message(project_description, documents)),
        ]

        logger.info(
            "Starting single-agent analysis",
            provider=settings.llm_provider.value,
        )

        start = time.perf_counter()
        markdown, raw_message = await self._invoke_llm(messages)
        elapsed = time.perf_counter() - start

        input_tokens, output_tokens = self._extract_tokens(raw_message)
        total_tokens = input_tokens + output_tokens

        provider = settings.llm_provider.value
        model = self._get_model_name()
        cost = estimate_cost(provider, model, input_tokens, output_tokens)

        metrics = {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "execution_time_seconds": round(elapsed, 3),
            "estimated_cost_usd": round(cost, 6),
        }

        logger.info(
            "Single-agent analysis complete",
            execution_time=f"{elapsed:.2f}s",
            total_tokens=total_tokens,
            cost=f"${cost:.4f}",
        )

        return {
            "markdown_content": markdown,
            "metrics": metrics,
        }

    async def _invoke_llm(self, messages: list) -> tuple[str, Any]:
        """Invoke the LLM and return (markdown_content, raw_ai_message).

        All providers use plain ainvoke() — no structured output.
        """
        raw_message = await self._llm.ainvoke(messages)
        markdown = self._extract_markdown(raw_message.content)
        return markdown, raw_message

    def _extract_markdown(self, content: str) -> str:
        """Strip accidental code-block wrappers from LLM output.

        Some models (especially Ollama) wrap the entire response in
        ```markdown ... ``` or ``` ... ``` despite being told not to.
        Uses rfind for the closing fence to preserve internal Mermaid fences.
        """
        content = content.strip()

        # Handle ```markdown fence (common from Ollama)
        if content.startswith("```markdown"):
            inner = content[len("```markdown"):]
            if "```" in inner:
                inner = inner[:inner.rfind("```")]
            return inner.strip()

        # Handle generic ``` fence wrapping the entire response
        # Only strip when count == 2 to avoid cutting internal Mermaid fences
        if content.startswith("```") and content.endswith("```") and content.count("```") == 2:
            inner = content[3:content.rfind("```")]
            return inner.strip()

        return content

    def _extract_tokens(self, raw_message: Any) -> tuple[int, int]:
        """Extract input and output token counts from the AI message."""
        usage = getattr(raw_message, "usage_metadata", None)
        if usage:
            return usage.get("input_tokens", 0), usage.get("output_tokens", 0)

        resp_meta = getattr(raw_message, "response_metadata", {})
        if "prompt_eval_count" in resp_meta:
            return (
                resp_meta.get("prompt_eval_count", 0),
                resp_meta.get("eval_count", 0),
            )

        logger.warning("Could not extract token usage from LLM response")
        return 0, 0

    def _get_model_name(self) -> str:
        """Return the active model name based on current provider settings."""
        match settings.llm_provider:
            case LLMProvider.OPENAI:
                return settings.openai_model
            case LLMProvider.ANTHROPIC:
                return settings.anthropic_model
            case LLMProvider.OLLAMA:
                return settings.ollama_model
            case _:
                return "unknown"
