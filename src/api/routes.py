"""API route definitions."""

from __future__ import annotations

from fastapi import APIRouter

from src.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.environment.value,
        "llm_provider": settings.llm_provider.value,
    }


# TODO: POST /analyze-project — single-shot analysis endpoint
# TODO: POST /sessions — create a new interactive session (clarification phase)
# TODO: POST /sessions/{session_id}/messages — send messages during clarification
# TODO: POST /sessions/{session_id}/generate — trigger architecture generation
