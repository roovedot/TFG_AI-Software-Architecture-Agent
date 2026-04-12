"""Validator & Aggregator Agent: validates coherence and consolidates the final report."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.base import BaseAgent
from src.llm.prompts import VALIDATOR_SYSTEM_PROMPT, format_multiagent_user_message
from src.llm.providers import get_llm

logger = structlog.get_logger()


class ValidatorAggregatorAgent(BaseAgent):
    """Decides whether to request a revision or produce the final markdown report."""

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
        return "ValidatorAggregator"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_description = state["project_description"]
        analysis_plan = state.get("analysis_plan", {})
        clarification_answers = state.get("clarification_answers") or None
        revision_count = int(state.get("revision_count", 0) or 0)

        agent_outputs = state.get("agent_outputs", {}) or {}
        requirements_output = agent_outputs.get("requirements")
        design_output = agent_outputs.get("designer")

        user_content = format_multiagent_user_message(
            project_description=project_description,
            clarification_answers=clarification_answers,
            analysis_plan=analysis_plan,
            requirements_output=requirements_output,
            design_output=design_output,
            revision_count=revision_count,
        )

        logger.info(
            "Validator: starting",
            provider=self._provider,
            model=self._model,
            revision_count=revision_count,
        )

        raw_text, metrics = await self._invoke_and_measure(
            VALIDATOR_SYSTEM_PROMPT, user_content
        )
        parsed = self._parse_json_output(raw_text)

        needs_revision = bool(parsed.get("needs_revision", False))
        revision_target = parsed.get("revision_target", "") or ""
        revision_feedback = parsed.get("revision_feedback", "") or ""
        markdown_content = parsed.get("markdown_content", "") or ""

        # Safety net: force termination when limit reached.
        if revision_count >= 2:
            needs_revision = False
            revision_target = ""
            if not markdown_content:
                logger.warning(
                    "Validator hit revision limit without producing markdown_content; "
                    "falling back to best-effort text"
                )
                markdown_content = (
                    "# Informe de Arquitectura (parcial)\n\n"
                    "No se pudo consolidar el informe final tras 2 rondas de revisión. "
                    "Se muestran a continuación los outputs de los agentes para revisión manual."
                )

        # When requesting a revision, DO NOT emit markdown_content (the graph
        # uses markdown presence as the termination signal).
        if needs_revision:
            markdown_content = ""
            new_revision_count = revision_count + 1
            current_step = f"revision_{new_revision_count}"
        else:
            new_revision_count = revision_count
            current_step = "validator"

        logger.info(
            "Validator: done",
            needs_revision=needs_revision,
            revision_target=revision_target,
            has_markdown=bool(markdown_content),
        )

        metrics_with_agent = {**metrics, "agent": self.name}
        existing_outputs = state.get("agent_outputs", {}) or {}
        existing_metrics = state.get("agent_metrics", []) or []

        return {
            "markdown_content": markdown_content,
            "revision_count": new_revision_count,
            "revision_target": revision_target,
            "revision_feedback": revision_feedback,
            "current_step": current_step,
            "validation_results": {
                "needs_revision": needs_revision,
                "revision_target": revision_target,
                "revision_feedback": revision_feedback,
            },
            "agent_outputs": {**existing_outputs, "validator": raw_text},
            "agent_metrics": [*existing_metrics, metrics_with_agent],
        }
