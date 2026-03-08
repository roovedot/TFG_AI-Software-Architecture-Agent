"""Single Agent (Baseline): generates a complete architecture report in one LLM call."""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.base import BaseAgent
from src.config import LLMProvider, settings
from src.llm.prompts import SINGLE_AGENT_SYSTEM_PROMPT, format_user_message
from src.llm.providers import get_llm
from src.models.output import AnalysisReport
from src.utils.cost import estimate_cost

logger = structlog.get_logger()


class SingleAgent(BaseAgent):
    """Baseline agent that produces a full AnalysisReport in a single LLM call.

    Uses structured output (function calling / tool use) for OpenAI and Anthropic,
    with a JSON-in-prompt fallback for Ollama.
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
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=format_user_message(project_description, documents)),
        ]

        logger.info(
            "Starting single-agent analysis",
            provider=settings.llm_provider.value,
        )

        start = time.perf_counter()
        report, raw_message = await self._invoke_llm(messages)
        elapsed = time.perf_counter() - start

        # Extract token usage from the raw AIMessage
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
            "final_report": report.model_dump(),
            "metrics": metrics,
        }

    def _build_system_prompt(self) -> str:
        """Build the system prompt, injecting JSON schema for Ollama."""
        if settings.llm_provider == LLMProvider.OLLAMA:
            schema = json.dumps(AnalysisReport.model_json_schema(), indent=2)
            return (
                f"{SINGLE_AGENT_SYSTEM_PROMPT}\n\n"
                "You MUST respond with valid JSON matching this exact schema:\n"
                f"```json\n{schema}\n```\n"
                "Respond ONLY with the JSON object, no additional text."
            )
        return SINGLE_AGENT_SYSTEM_PROMPT

    async def _invoke_llm(self, messages: list) -> tuple[AnalysisReport, Any]:
        """Invoke the LLM and return (parsed_report, raw_ai_message).

        Uses with_structured_output for OpenAI/Anthropic, with a manual
        JSON parsing fallback for Ollama.
        """
        if settings.llm_provider == LLMProvider.OLLAMA:
            return await self._invoke_ollama_fallback(messages)

        structured_llm = self._llm.with_structured_output(
            AnalysisReport, include_raw=True
        )
        result = await structured_llm.ainvoke(messages)
        return result["parsed"], result["raw"]

    async def _invoke_ollama_fallback(
        self, messages: list
    ) -> tuple[AnalysisReport, Any]:
        """Fallback for Ollama: prompt-based JSON generation + manual parsing."""
        raw_message = await self._llm.ainvoke(messages)
        content = raw_message.content

        # Try to extract JSON from the response (may be wrapped in ```json blocks)
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        report = AnalysisReport.model_validate_json(json_str.strip())
        return report, raw_message

    def _extract_tokens(self, raw_message: Any) -> tuple[int, int]:
        """Extract input and output token counts from the AI message."""
        # LangChain populates usage_metadata for OpenAI and Anthropic
        usage = getattr(raw_message, "usage_metadata", None)
        if usage:
            return usage.get("input_tokens", 0), usage.get("output_tokens", 0)

        # Ollama: check response_metadata
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
