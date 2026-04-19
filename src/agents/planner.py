"""Planner Agent: analyzes input, asks clarification questions, creates an analysis plan."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.base import BaseAgent
from src.llm.prompts import PLANNER_SYSTEM_PROMPT, format_multiagent_user_message
from src.llm.providers import get_llm

logger = structlog.get_logger()


class PlannerAgent(BaseAgent):
    """First agent in the multiagent pipeline.

    Always produces 3 to 5 clarification questions plus an `analysis_plan`
    that downstream agents use as guidance.
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
        return "Planner"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_description = state["project_description"]
        documents = state.get("user_documents", [])
        images = state.get("user_images", [])

        user_content = format_multiagent_user_message(
            project_description=project_description,
            documents=documents,
            images=images,
        )

        logger.info("Planner: starting analysis", provider=self._provider, model=self._model)
        raw_text, metrics = await self._invoke_and_measure(
            PLANNER_SYSTEM_PROMPT, user_content
        )
        parsed = self._parse_json_output(raw_text)

        questions = parsed.get("questions", []) or []
        analysis_plan = parsed.get("analysis_plan", {}) or {}

        logger.info("Planner: done", num_questions=len(questions))

        metrics_with_agent = {**metrics, "agent": self.name}
        existing_outputs = state.get("agent_outputs", {}) or {}
        existing_metrics = state.get("agent_metrics", []) or []

        return {
            "analysis_plan": analysis_plan,
            "clarification_questions": questions,
            "current_step": "planner",
            "agent_outputs": {**existing_outputs, "planner": raw_text},
            "agent_metrics": [*existing_metrics, metrics_with_agent],
        }
