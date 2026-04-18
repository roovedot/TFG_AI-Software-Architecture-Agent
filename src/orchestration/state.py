"""Shared state definition for the agent pipeline."""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    """State shared between all agents in the LangGraph pipeline.

    This state flows through the agent graph and accumulates
    results from each agent's processing step.
    """

    # User input
    project_description: str
    user_documents: list[str]
    user_images: list[dict]
    session_id: str

    # Multiagent runtime context
    project_id: str
    current_step: str  # "planner" | "requirements" | "designer" | "validator" | "revision_1" | "revision_2"
    agent_configs: dict[str, dict[str, str]]  # {"planner": {"provider": ..., "model": ...}, ...}

    # Clarification phase
    clarification_questions: list[dict]  # [{"question": str, "options": list[str]}]
    clarification_answers: dict[str, str]
    clarification_complete: bool

    # Planner output
    analysis_plan: dict[str, Any]

    # Requirements & Tech Stack output
    requirements: dict[str, Any]
    tech_stack: dict[str, Any]

    # Architecture Designer output
    architecture: dict[str, Any]

    # Validator & Aggregator output
    validation_results: dict[str, Any]
    markdown_content: str

    # Feedback loop control
    revision_count: int
    revision_target: str  # "" | "requirements" | "designer"
    revision_feedback: str

    # Per-agent outputs and metrics (for frontend display)
    agent_outputs: dict[str, str]  # agent_name -> raw output
    agent_metrics: list[dict]  # list of per-agent LLMMetrics dicts

    # Aggregated metrics (baseline compatibility)
    metrics: dict[str, Any]

    # Metadata
    errors: list[str]
