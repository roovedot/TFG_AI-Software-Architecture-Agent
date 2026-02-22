"""Pydantic models for API input validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectInput(BaseModel):
    """Input model for project analysis requests."""

    description: str = Field(
        ...,
        min_length=10,
        description="Project description or requirements document text.",
    )
    documents: list[str] = Field(
        default_factory=list,
        description="Additional documents (as text) providing project context.",
    )


class ClarificationResponse(BaseModel):
    """User's response to clarification questions."""

    session_id: str
    answers: dict[str, str] = Field(
        ...,
        description="Mapping of question -> answer for each clarification question.",
    )
