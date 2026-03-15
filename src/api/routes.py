"""API route definitions."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from src.config import settings
from src.models.input import ProjectInput
from src.models.metrics import BaselineResult, LLMMetrics
from src.orchestration.single_graph import build_single_agent_graph

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.environment.value,
        "llm_provider": settings.llm_provider.value,
    }


@router.post("/analyze/baseline", response_model=BaselineResult)
async def analyze_baseline(project_input: ProjectInput) -> BaselineResult:
    """Run the single-agent baseline analysis on a project description."""
    try:
        graph = build_single_agent_graph()
        initial_state = {
            "project_description": project_input.description,
            "user_documents": project_input.documents,
        }
        result = await graph.ainvoke(initial_state)

        return BaselineResult(
            markdown_content=result["markdown_content"],
            metrics=LLMMetrics.model_validate(result["metrics"]),
        )
    except Exception as e:
        logger.error("Baseline analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e


# TODO: POST /sessions — create a new interactive session (clarification phase)
# TODO: POST /sessions/{session_id}/messages — send messages during clarification
# TODO: POST /sessions/{session_id}/generate — trigger architecture generation
