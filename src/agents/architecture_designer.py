"""Architecture Designer Agent: designs the software architecture."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent


class ArchitectureDesignerAgent(BaseAgent):
    """Designs the software architecture based on requirements and tech stack.

    Responsibilities:
    - Design architecture pattern (microservices, monolith, serverless, etc.)
    - Define infrastructure components
    - Propose design patterns
    - Generate architecture descriptions
    """

    @property
    def name(self) -> str:
        return "ArchitectureDesigner"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
