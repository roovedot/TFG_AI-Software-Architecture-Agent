"""Architecture Designer Agent: produces patterns, components, diagram, risks, plan."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.base import BaseAgent
from src.llm.prompts import DESIGNER_SYSTEM_PROMPT, format_multiagent_user_message
from src.llm.providers import get_llm

logger = structlog.get_logger()


class ArchitectureDesignerAgent(BaseAgent):
    """Designs the system architecture based on the Planner + Requirements outputs."""

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
        return "ArchitectureDesigner"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_description = state["project_description"]
        analysis_plan = state.get("analysis_plan", {})
        clarification_answers = state.get("clarification_answers") or None

        # Pass the Requirements agent's raw JSON output as context.
        agent_outputs = state.get("agent_outputs", {}) or {}
        requirements_output = agent_outputs.get("requirements")

        revision_target = state.get("revision_target", "")
        revision_feedback: str | None = None
        if revision_target == "designer":
            revision_feedback = state.get("revision_feedback") or None

        user_content = format_multiagent_user_message(
            project_description=project_description,
            clarification_answers=clarification_answers,
            analysis_plan=analysis_plan,
            requirements_output=requirements_output,
            revision_feedback=revision_feedback,
        )

        is_revision = revision_feedback is not None
        logger.info(
            "Designer: starting",
            provider=self._provider,
            model=self._model,
            is_revision=is_revision,
        )

        raw_text, metrics = await self._invoke_and_measure(
            DESIGNER_SYSTEM_PROMPT, user_content
        )
        parsed = self._parse_json_output(raw_text)

        logger.info("Designer: done")

        metrics_with_agent = {**metrics, "agent": self.name}
        existing_outputs = state.get("agent_outputs", {}) or {}
        existing_metrics = state.get("agent_metrics", []) or []

        return {
            "architecture": parsed,
            "current_step": "designer",
            "agent_outputs": {**existing_outputs, "designer": raw_text},
            "agent_metrics": [*existing_metrics, metrics_with_agent],
            "revision_feedback": "" if is_revision else state.get("revision_feedback", ""),
            "revision_target": "" if is_revision else state.get("revision_target", ""),
        }
