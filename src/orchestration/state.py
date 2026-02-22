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
    session_id: str

    # Clarification phase
    clarification_questions: list[str]
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
    final_report: dict[str, Any]

    # Metadata
    errors: list[str]
