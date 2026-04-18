"""Base agent class defining the common interface and shared LLM helpers."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.utils.cost import estimate_cost

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base class for all agents in the pipeline."""

    # Subclasses that reuse the shared helpers must set these in __init__.
    _llm: BaseChatModel
    _provider: str | None = None
    _model: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name for logging and tracing."""

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task and return a partial state update.

        Args:
            state: The shared state dictionary passed through the agent pipeline.

        Returns:
            A partial state dict that LangGraph will merge into the main state.
        """

    # ------------------------------------------------------------------
    # Shared helpers (used by both SingleAgent and the multiagent agents)
    # ------------------------------------------------------------------

    async def _invoke_and_measure(
        self,
        system_prompt: str,
        user_content: str | list[dict],
    ) -> tuple[str, dict]:
        """Invoke the LLM once and return (raw_text, metrics_dict).

        The metrics dict has the same shape used everywhere else in the system:
        provider, model, input/output/total tokens, execution time, cost.
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        provider = self._provider or "unknown"
        model = self._model or "unknown"

        start = time.perf_counter()
        raw_message = await self._llm.ainvoke(messages)
        elapsed = time.perf_counter() - start

        input_tokens, output_tokens = self._extract_tokens(raw_message)
        total_tokens = input_tokens + output_tokens
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

        content = raw_message.content
        if isinstance(content, list):
            # Some providers return content as a list of blocks — flatten text.
            content = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )

        return content, metrics

    def _extract_tokens(self, raw_message: Any) -> tuple[int, int]:
        """Extract input and output token counts from an AI message.

        Handles both the OpenAI/Anthropic `usage_metadata` shape and the
        Ollama `response_metadata` shape (`prompt_eval_count`/`eval_count`).
        """
        usage = getattr(raw_message, "usage_metadata", None)
        if usage:
            return usage.get("input_tokens", 0), usage.get("output_tokens", 0)

        resp_meta = getattr(raw_message, "response_metadata", {})
        if "prompt_eval_count" in resp_meta:
            return (
                resp_meta.get("prompt_eval_count", 0),
                resp_meta.get("eval_count", 0),
            )

        logger.warning(
            "Could not extract token usage from LLM response",
            agent=self.name,
        )
        return 0, 0

    def _parse_json_output(self, raw_text: str) -> dict:
        """Parse a JSON object from the LLM's raw response.

        Tolerates:
        - Leading/trailing whitespace.
        - ```json ... ``` or plain ``` ... ``` code fences.
        - Prose before/after the JSON block (best-effort: uses first '{' to
          last '}' as a fallback).

        Raises ValueError if no valid JSON object can be extracted.
        """
        text = raw_text.strip()

        # Strip fenced blocks.
        if text.startswith("```"):
            # Drop the first line (```json or ```), drop the trailing ```.
            lines = text.split("\n")
            if len(lines) >= 2:
                text = "\n".join(lines[1:])
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: slice from first '{' to last '}'.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{self.name}: failed to parse JSON from LLM output: {exc}"
                ) from exc

        raise ValueError(f"{self.name}: no JSON object found in LLM output")
