"""Base agent class defining the common interface for all agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all agents in the pipeline."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name for logging and tracing."""

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task and return the updated state.

        Args:
            state: The shared state dictionary passed through the agent pipeline.

        Returns:
            The updated state dictionary with this agent's contributions.
        """
