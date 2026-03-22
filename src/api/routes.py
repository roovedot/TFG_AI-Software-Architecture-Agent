"""API route definitions."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.config import settings
from src.db import repositories as repo
from src.llm.models import get_available_models
from src.models.metrics import LLMMetrics
from src.models.project import AnalyzeResponse, ProjectDetail, ProjectRating, ProjectSummary
from src.orchestration.single_graph import build_single_agent_graph
from src.utils.file_processing import process_uploaded_file

logger = structlog.get_logger()

router = APIRouter()


# ── Health & Models ──────────────────────────────────────────────────────────


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


# ── Analysis ─────────────────────────────────────────────────────────────────


@router.post("/analyze/baseline", response_model=AnalyzeResponse)
async def analyze_baseline(
    description: str = Form(..., min_length=10),
    provider: str = Form(...),
    model: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> AnalyzeResponse:
    """Run the single-agent baseline analysis and persist the project."""
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

        # Read raw bytes for GridFS storage before processing
        files_data: list[dict] = []
        for f in files:
            content = await f.read()
            files_data.append({
                "name": f.filename or "unknown",
                "content": content,
                "content_type": f.content_type or "application/octet-stream",
                "size": len(content),
            })
            await f.seek(0)  # Reset for process_uploaded_file

        # Process uploaded files for LLM
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

        metrics = result["metrics"]
        markdown_content = result["markdown_content"]

        # Persist project to MongoDB
        project_id = await repo.create_project(
            description=description,
            provider=provider,
            model=model,
            files_data=files_data,
            markdown_content=markdown_content,
            metrics=metrics,
        )

        return AnalyzeResponse(
            project_id=project_id,
            markdown_content=markdown_content,
            metrics=LLMMetrics.model_validate(metrics),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Baseline analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e


# ── Projects ─────────────────────────────────────────────────────────────────


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects():
    """Return all projects as summaries for the history sidebar."""
    return await repo.list_projects()


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str):
    """Return full project details."""
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and its associated GridFS files."""
    deleted = await repo.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


@router.put("/projects/{project_id}/ratings")
async def update_ratings(project_id: str, ratings: ProjectRating):
    """Save or update ratings for a project."""
    updated = await repo.update_ratings(project_id, ratings.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "updated"}


@router.get("/projects/{project_id}/files/{file_id}")
async def download_file(project_id: str, file_id: str):
    """Download a file from GridFS that belongs to a project."""
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify the file belongs to this project
    file_ids = {f["file_id"] for f in project.get("files", [])}
    if file_id not in file_ids:
        raise HTTPException(status_code=404, detail="File not found in this project")

    stream, metadata = await repo.get_project_file(file_id)
    return StreamingResponse(
        stream,
        media_type=metadata["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{metadata["name"]}"'},
    )
