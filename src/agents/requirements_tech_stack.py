"""Requirements & Tech Stack Agent: extracts requirements and recommends technologies."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.base import BaseAgent
from src.llm.prompts import REQUIREMENTS_SYSTEM_PROMPT, format_multiagent_user_message
from src.llm.providers import get_llm

logger = structlog.get_logger()


class RequirementsTechStackAgent(BaseAgent):
    """Produces structured requirements and a justified tech stack in JSON."""

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
        return "RequirementsTechStack"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_description = state["project_description"]
        analysis_plan = state.get("analysis_plan", {})
        clarification_answers = state.get("clarification_answers") or None

        # Only include revision feedback if this is a revision pass targeting us.
        revision_target = state.get("revision_target", "")
        revision_feedback: str | None = None
        if revision_target == "requirements":
            revision_feedback = state.get("revision_feedback") or None

        user_content = format_multiagent_user_message(
            project_description=project_description,
            documents=state.get("user_documents", []),
            clarification_answers=clarification_answers,
            analysis_plan=analysis_plan,
            revision_feedback=revision_feedback,
        )

        is_revision = revision_feedback is not None
        logger.info(
            "Requirements: starting",
            provider=self._provider,
            model=self._model,
            is_revision=is_revision,
        )

        raw_text, metrics = await self._invoke_and_measure(
            REQUIREMENTS_SYSTEM_PROMPT, user_content
        )
        parsed = self._parse_json_output(raw_text)

        logger.info("Requirements: done")

        metrics_with_agent = {**metrics, "agent": self.name}
        existing_outputs = state.get("agent_outputs", {}) or {}
        existing_metrics = state.get("agent_metrics", []) or []

        return {
            "requirements": {
                "functional": parsed.get("functional_requirements", []),
                "non_functional": parsed.get("non_functional_requirements", []),
            },
            "tech_stack": {
                "items": parsed.get("tech_stack", []),
                "notes": parsed.get("notes", ""),
            },
            "current_step": "requirements",
            "agent_outputs": {**existing_outputs, "requirements": raw_text},
            "agent_metrics": [*existing_metrics, metrics_with_agent],
            # Clear revision_feedback after consuming it so downstream nodes
            # don't see stale guidance.
            "revision_feedback": "" if is_revision else state.get("revision_feedback", ""),
            "revision_target": "" if is_revision else state.get("revision_target", ""),
        }
