"""Models for project persistence, ratings, and API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.metrics import LLMMetrics


class AgentConfig(BaseModel):
    """Provider/model pair for a single agent in the multiagent pipeline."""

    provider: str
    model: str


class MultiagentConfigs(BaseModel):
    """Per-agent provider/model configuration for the 4-agent pipeline."""

    planner: AgentConfig
    requirements: AgentConfig
    designer: AgentConfig
    validator: AgentConfig


class ClarificationQuestion(BaseModel):
    """A question the Planner asks the user, with suggested options + free-form 'Other'."""

    question: str
    options: list[str] = Field(default_factory=list)


class ClarificationSubmission(BaseModel):
    """User response payload for POST /projects/{id}/clarification."""

    answers: dict[str, str]


class AgentOutput(BaseModel):
    """Raw textual output produced by an individual agent."""

    agent_name: str
    content: str


class ChatMessage(BaseModel):
    """A single message in the post-generation chat."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime
    metrics: LLMMetrics | None = None


class ChatRequest(BaseModel):
    """Payload for POST /projects/{id}/chat."""

    message: str
    provider: str
    model: str


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
    status: str  # "processing" | "waiting_clarification" | "completed" | "error"
    has_rating: bool
    pipeline_type: str = "baseline"  # "baseline" | "multiagent"


class ProjectDetail(BaseModel):
    """Full project data for the detail view."""

    id: str
    created_at: datetime
    description: str
    provider: str
    model: str
    status: str  # "processing" | "waiting_clarification" | "completed" | "error"
    error_message: str | None = None
    files: list[FileReference]
    markdown_content: str | None = None
    metrics: LLMMetrics | None = None
    ratings: ProjectRating | None = None

    # Multiagent-only fields
    pipeline_type: str = "baseline"
    current_step: str | None = None
    agent_configs: MultiagentConfigs | None = None
    clarification_questions: list[ClarificationQuestion] | None = None
    clarification_answers: dict[str, str] | None = None
    agent_outputs: dict[str, str] | None = None
    agent_metrics: list[LLMMetrics] | None = None
    chat_history: list[ChatMessage] | None = None


class AnalyzeResponse(BaseModel):
    """Response from the analyze endpoint — returns immediately with project ID."""

    project_id: str
    status: str = "processing"
