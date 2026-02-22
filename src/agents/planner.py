"""Planner Agent: analyzes input and creates an analysis plan."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent


class PlannerAgent(BaseAgent):
    """Analyzes the project input and creates a structured analysis plan.

    Responsibilities:
    - Parse and understand the project description
    - Identify what information is missing or ambiguous
    - Generate clarification questions for the user
    - Create an analysis plan for downstream agents
    """

    @property
    def name(self) -> str:
        return "Planner"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
