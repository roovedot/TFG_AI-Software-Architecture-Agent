"""Validator & Aggregator Agent: validates coherence and consolidates the final report."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent


class ValidatorAggregatorAgent(BaseAgent):
    """Validates coherence and consolidates the final report.

    Responsibilities:
    - Verify coherence between requirements, tech stack, and architecture
    - Identify risks and conflicts
    - Validate feasibility
    - Consolidate the final structured report
    """

    @property
    def name(self) -> str:
        return "ValidatorAggregator"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
