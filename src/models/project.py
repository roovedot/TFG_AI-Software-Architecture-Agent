"""Models for project persistence, ratings, and API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.metrics import LLMMetrics


class FileReference(BaseModel):
    """Reference to a file stored in GridFS."""

    file_id: str
    name: str
    size: int
    content_type: str


class ProjectRating(BaseModel):
    """User evaluation of a generated architecture report."""

    identifies_right_concerns: int = Field(..., ge=0, le=10)
    adherence_to_request: int = Field(..., ge=0, le=10)
    completeness_of_analysis: int = Field(..., ge=0, le=10)
    tech_stack_quality: int = Field(..., ge=0, le=10)
    document_clarity: int = Field(..., ge=0, le=10)
    risk_identification: int = Field(..., ge=0, le=10)
    actionability: int = Field(..., ge=0, le=10)
    comments: str = ""


class ProjectSummary(BaseModel):
    """Lightweight project info for the history sidebar."""

    id: str
    created_at: datetime
    description_preview: str
    provider: str
    model: str
    status: str  # "processing" | "completed" | "error"
    has_rating: bool


class ProjectDetail(BaseModel):
    """Full project data for the detail view."""

    id: str
    created_at: datetime
    description: str
    provider: str
    model: str
    status: str  # "processing" | "completed" | "error"
    error_message: str | None = None
    files: list[FileReference]
    markdown_content: str | None = None
    metrics: LLMMetrics | None = None
    ratings: ProjectRating | None = None


class AnalyzeResponse(BaseModel):
    """Response from the analyze endpoint — returns immediately with project ID."""

    project_id: str
    status: str = "processing"
