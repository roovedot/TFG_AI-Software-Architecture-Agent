"""Pydantic models for structured output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TechRecommendation(BaseModel):
    """A single technology recommendation with justification."""

    category: str = Field(..., description="E.g., 'backend_framework', 'database', 'frontend'.")
    name: str
    justification: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    """A classified project requirement."""

    description: str
    type: str = Field(..., description="'functional' or 'non_functional'.")
    priority: str = Field(..., description="'must_have', 'should_have', or 'nice_to_have'.")


class ArchitectureProposal(BaseModel):
    """Architecture design proposal."""

    pattern: str = Field(..., description="E.g., 'microservices', 'monolith', 'serverless'.")
    justification: str
    components: list[dict] = Field(default_factory=list)
    design_patterns: list[str] = Field(default_factory=list)
    infrastructure: dict = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    """Identified risk with mitigation strategy."""

    risk: str
    severity: str = Field(..., description="'high', 'medium', or 'low'.")
    mitigation: str


class AnalysisReport(BaseModel):
    """Final consolidated analysis report."""

    requirements: list[Requirement] = Field(default_factory=list)
    tech_stack: list[TechRecommendation] = Field(default_factory=list)
    architecture: ArchitectureProposal | None = None
    risks: list[RiskAssessment] = Field(default_factory=list)
    development_plan: list[dict] = Field(default_factory=list)
    summary: str = ""
