"""Requirements & Tech Stack Agent: extracts requirements and recommends technologies."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent


class RequirementsTechStackAgent(BaseAgent):
    """Extracts requirements and recommends a technology stack.

    Responsibilities:
    - Extract functional and non-functional requirements
    - Classify requirements by priority
    - Recommend technology stack (frameworks, libraries, databases)
    - Justify decisions with pros/cons
    """

    @property
    def name(self) -> str:
        return "RequirementsTechStack"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
