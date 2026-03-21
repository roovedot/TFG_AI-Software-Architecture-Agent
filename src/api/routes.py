"""API route definitions."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.config import settings
from src.llm.models import get_available_models
from src.models.metrics import BaselineResult, LLMMetrics
from src.orchestration.single_graph import build_single_agent_graph
from src.utils.file_processing import process_uploaded_file

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.environment.value,
        "llm_provider": settings.llm_provider.value,
    }


@router.get("/models")
async def list_models():
    """Return the list of available LLM models based on environment and API keys."""
    models = get_available_models()
    return [
        {
            "provider": m.provider,
            "model_id": m.model_id,
            "label": m.label,
            "tier": m.tier,
            "supports_vision": m.supports_vision,
        }
        for m in models
    ]


@router.post("/analyze/baseline", response_model=BaselineResult)
async def analyze_baseline(
    description: str = Form(..., min_length=10),
    provider: str = Form(...),
    model: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> BaselineResult:
    """Run the single-agent baseline analysis on a project description."""
    try:
        # Validate model selection
        available = get_available_models()
        valid = any(m.model_id == model and m.provider == provider for m in available)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail=f"Model {provider}/{model} is not available. "
                f"Check API keys and environment.",
            )

        # Reject files for non-vision models (Ollama)
        if provider == "ollama" and files:
            raise HTTPException(
                status_code=400,
                detail="File upload is not supported with local Ollama models.",
            )

        # Process uploaded files
        documents: list[str] = []
        images: list[dict] = []
        for f in files:
            text, img = await process_uploaded_file(f)
            if text:
                documents.append(text)
            if img:
                images.append(img)

        # Build and invoke graph
        graph = build_single_agent_graph(provider=provider, model=model)
        initial_state = {
            "project_description": description,
            "user_documents": documents,
            "user_images": images,
        }
        result = await graph.ainvoke(initial_state)

        return BaselineResult(
            markdown_content=result["markdown_content"],
            metrics=LLMMetrics.model_validate(result["metrics"]),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Baseline analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e


# TODO: POST /sessions — create a new interactive session (clarification phase)
# TODO: POST /sessions/{session_id}/messages — send messages during clarification
# TODO: POST /sessions/{session_id}/generate — trigger architecture generation
