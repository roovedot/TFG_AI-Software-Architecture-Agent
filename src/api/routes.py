"""API route definitions."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.config import settings
from src.db import repositories as repo
from src.llm.models import get_available_models
from src.models.project import (
    AnalyzeResponse,
    ClarificationSubmission,
    ProjectDetail,
    ProjectRating,
    ProjectSummary,
)
from src.orchestration.graph import build_pipeline_graph, build_planner_graph
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


async def _run_analysis(
    project_id: str,
    provider: str,
    model: str,
    description: str,
    documents: list[str],
    images: list[dict],
) -> None:
    """Background task: run LLM analysis and update the project with results."""
    try:
        graph = build_single_agent_graph(provider=provider, model=model)
        initial_state = {
            "project_description": description,
            "user_documents": documents,
            "user_images": images,
        }
        result = await graph.ainvoke(initial_state)
        await repo.complete_project(
            project_id,
            markdown_content=result["markdown_content"],
            metrics=result["metrics"],
        )
        logger.info("Analysis completed", project_id=project_id)
    except Exception as e:
        logger.error("Analysis failed", project_id=project_id, error=str(e))
        await repo.fail_project(project_id, error_message=str(e))


@router.post("/analyze/baseline", response_model=AnalyzeResponse)
async def analyze_baseline(
    description: str = Form(..., min_length=10),
    provider: str = Form(...),
    model: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> AnalyzeResponse:
    """Start a baseline analysis. Returns immediately with a project ID.

    The analysis runs in the background. Poll GET /projects/{id} to check status.
    """
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

    # Process uploaded files for LLM (text extraction, image encoding)
    documents: list[str] = []
    images: list[dict] = []
    for f in files:
        text, img = await process_uploaded_file(f)
        if text:
            documents.append(text)
        if img:
            images.append(img)

    # Create project immediately with status "processing"
    project_id = await repo.create_project(
        description=description,
        provider=provider,
        model=model,
        files_data=files_data,
        status="processing",
    )

    # Fire off analysis in background
    asyncio.create_task(
        _run_analysis(project_id, provider, model, description, documents, images)
    )

    return AnalyzeResponse(project_id=project_id, status="processing")


# ── Multiagent analysis ──────────────────────────────────────────────────────


def _aggregate_metrics(agent_metrics: list[dict]) -> dict:
    """Sum per-agent metrics into a single aggregated record for the project."""
    if not agent_metrics:
        return {
            "provider": "multiagent",
            "model": "multiple",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "execution_time_seconds": 0.0,
            "estimated_cost_usd": 0.0,
        }
    input_tokens = sum(m.get("input_tokens", 0) for m in agent_metrics)
    output_tokens = sum(m.get("output_tokens", 0) for m in agent_metrics)
    exec_time = sum(m.get("execution_time_seconds", 0.0) for m in agent_metrics)
    cost = sum(m.get("estimated_cost_usd", 0.0) for m in agent_metrics)
    providers = {m.get("provider", "") for m in agent_metrics}
    models = {m.get("model", "") for m in agent_metrics}
    return {
        "provider": next(iter(providers)) if len(providers) == 1 else "multiagent",
        "model": next(iter(models)) if len(models) == 1 else "multiple",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "execution_time_seconds": round(exec_time, 3),
        "estimated_cost_usd": round(cost, 6),
    }


async def _run_planner_phase(
    project_id: str,
    agent_configs: dict,
    description: str,
    documents: list[str],
    images: list[dict],
) -> None:
    """Background task: run the Planner. If clarification is needed, stop and wait.

    Otherwise, chain directly into the pipeline phase.
    """
    try:
        planner_cfg = agent_configs["planner"]
        graph = build_planner_graph(
            provider=planner_cfg["provider"], model=planner_cfg["model"]
        )
        initial_state = {
            "project_id": project_id,
            "project_description": description,
            "user_documents": documents,
            "user_images": images,
            "agent_configs": agent_configs,
            "revision_count": 0,
            "revision_target": "",
            "revision_feedback": "",
            "agent_outputs": {},
            "agent_metrics": [],
        }
        result = await graph.ainvoke(initial_state)

        # Persist planner output + metrics.
        planner_output = (result.get("agent_outputs", {}) or {}).get("planner", "")
        if planner_output:
            await repo.save_agent_output(project_id, "planner", planner_output)
        planner_metrics = result.get("agent_metrics") or []
        if planner_metrics:
            await repo.save_agent_metrics(project_id, planner_metrics)

        questions = result.get("clarification_questions", []) or []
        analysis_plan = result.get("analysis_plan") or {}
        if questions:
            await repo.set_clarification_questions(
                project_id, questions, analysis_plan=analysis_plan
            )
            logger.info(
                "Planner produced clarification questions",
                project_id=project_id,
                num_questions=len(questions),
            )
            return

        # No clarification needed — run the pipeline phase right away.
        await _run_pipeline_phase(
            project_id=project_id,
            agent_configs=agent_configs,
            description=description,
            documents=documents,
            images=images,
            analysis_plan=result.get("analysis_plan", {}),
            clarification_answers=None,
            carryover_outputs=result.get("agent_outputs", {}) or {},
            carryover_metrics=result.get("agent_metrics", []) or [],
        )
    except Exception as e:
        logger.error("Planner phase failed", project_id=project_id, error=str(e))
        await repo.fail_project(project_id, error_message=str(e))


async def _run_pipeline_phase(
    project_id: str,
    agent_configs: dict,
    description: str,
    documents: list[str],
    images: list[dict],
    analysis_plan: dict,
    clarification_answers: dict[str, str] | None,
    carryover_outputs: dict | None = None,
    carryover_metrics: list[dict] | None = None,
) -> None:
    """Background task: run requirements → designer → validator (with revision loop)."""
    try:
        carryover_outputs = carryover_outputs or {}
        carryover_metrics = carryover_metrics or []

        req_cfg = agent_configs["requirements"]
        des_cfg = agent_configs["designer"]
        val_cfg = agent_configs["validator"]

        graph = build_pipeline_graph(
            requirements_provider=req_cfg["provider"],
            requirements_model=req_cfg["model"],
            designer_provider=des_cfg["provider"],
            designer_model=des_cfg["model"],
            validator_provider=val_cfg["provider"],
            validator_model=val_cfg["model"],
        )

        await repo.update_current_step(project_id, "requirements")

        initial_state = {
            "project_id": project_id,
            "project_description": description,
            "user_documents": documents,
            "user_images": images,
            "analysis_plan": analysis_plan,
            "clarification_answers": clarification_answers or {},
            "clarification_complete": True,
            "agent_configs": agent_configs,
            "revision_count": 0,
            "revision_target": "",
            "revision_feedback": "",
            "agent_outputs": dict(carryover_outputs),
            "agent_metrics": list(carryover_metrics),
        }

        # Stream node-by-node so we can persist outputs and progress in real time.
        seen_outputs: dict[str, str] = dict(carryover_outputs)
        result: dict = {}

        async for event in graph.astream(initial_state, stream_mode="values"):
            result = event
            # Update current_step based on state (agents set it themselves).
            step = event.get("current_step", "")
            if step:
                await repo.update_current_step(project_id, step)
            # Persist any new agent outputs produced in this step.
            outputs = event.get("agent_outputs", {}) or {}
            for name, content in outputs.items():
                if seen_outputs.get(name) == content:
                    continue
                seen_outputs[name] = content
                await repo.save_agent_output(project_id, name, content)
            # Overwrite full metrics array (not push) to avoid duplicates.
            metrics_list = event.get("agent_metrics", []) or []
            if metrics_list:
                await repo.save_agent_metrics(project_id, metrics_list)

        final_metrics = result.get("agent_metrics", []) or []

        markdown = result.get("markdown_content", "") or ""
        if not markdown:
            raise RuntimeError(
                "Pipeline terminated without producing markdown_content"
            )

        aggregated = _aggregate_metrics(final_metrics)
        await repo.complete_multiagent_project(
            project_id, markdown_content=markdown, aggregated_metrics=aggregated
        )
        logger.info("Multiagent analysis completed", project_id=project_id)
    except Exception as e:
        logger.error("Pipeline phase failed", project_id=project_id, error=str(e))
        await repo.fail_project(project_id, error_message=str(e))


def _parse_agent_configs(
    planner_provider: str,
    planner_model: str,
    requirements_provider: str,
    requirements_model: str,
    designer_provider: str,
    designer_model: str,
    validator_provider: str,
    validator_model: str,
) -> dict:
    available = get_available_models()
    pairs = {(m.provider, m.model_id) for m in available}

    configs = {
        "planner": {"provider": planner_provider, "model": planner_model},
        "requirements": {"provider": requirements_provider, "model": requirements_model},
        "designer": {"provider": designer_provider, "model": designer_model},
        "validator": {"provider": validator_provider, "model": validator_model},
    }
    for agent_name, cfg in configs.items():
        if (cfg["provider"], cfg["model"]) not in pairs:
            raise HTTPException(
                status_code=400,
                detail=f"Model {cfg['provider']}/{cfg['model']} not available for agent '{agent_name}'.",
            )
    return configs


@router.post("/analyze/multiagent", response_model=AnalyzeResponse)
async def analyze_multiagent(
    description: str = Form(..., min_length=10),
    planner_provider: str = Form(...),
    planner_model: str = Form(...),
    requirements_provider: str = Form(...),
    requirements_model: str = Form(...),
    designer_provider: str = Form(...),
    designer_model: str = Form(...),
    validator_provider: str = Form(...),
    validator_model: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> AnalyzeResponse:
    """Start a multiagent analysis. Runs planner first; may pause for clarification."""
    agent_configs = _parse_agent_configs(
        planner_provider,
        planner_model,
        requirements_provider,
        requirements_model,
        designer_provider,
        designer_model,
        validator_provider,
        validator_model,
    )

    # Ollama does not support multimodal file input in our setup.
    any_ollama = any(cfg["provider"] == "ollama" for cfg in agent_configs.values())
    if any_ollama and files:
        raise HTTPException(
            status_code=400,
            detail="File upload is not supported when any agent uses local Ollama models.",
        )

    # Read raw bytes for GridFS + process for LLM input.
    files_data: list[dict] = []
    for f in files:
        content = await f.read()
        files_data.append({
            "name": f.filename or "unknown",
            "content": content,
            "content_type": f.content_type or "application/octet-stream",
            "size": len(content),
        })
        await f.seek(0)

    documents: list[str] = []
    images: list[dict] = []
    for f in files:
        text, img = await process_uploaded_file(f)
        if text:
            documents.append(text)
        if img:
            images.append(img)

    project_id = await repo.create_multiagent_project(
        description=description,
        agent_configs=agent_configs,
        files_data=files_data,
        processed_documents=documents,
        processed_images=images,
    )

    asyncio.create_task(
        _run_planner_phase(project_id, agent_configs, description, documents, images)
    )

    return AnalyzeResponse(project_id=project_id, status="processing")


@router.post("/projects/{project_id}/clarification")
async def submit_clarification(project_id: str, submission: ClarificationSubmission):
    """Accept user's clarification answers and resume the pipeline."""
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("status") != "waiting_clarification":
        raise HTTPException(
            status_code=400,
            detail=f"Project is in status '{project.get('status')}', not 'waiting_clarification'",
        )

    await repo.submit_clarification_answers(project_id, submission.answers)

    agent_configs = project.get("agent_configs") or {}
    description = project.get("description", "")
    documents = project.get("processed_documents") or []
    images = project.get("processed_images") or []

    # analysis_plan was stored directly in Mongo by set_clarification_questions.
    plan: dict = project.get("analysis_plan") or {}

    # Re-seed carryover so the frontend keeps seeing the planner output.
    planner_raw = (project.get("agent_outputs") or {}).get("planner")
    carryover_outputs = {"planner": planner_raw} if planner_raw else {}
    carryover_metrics = list(project.get("agent_metrics") or [])

    asyncio.create_task(
        _run_pipeline_phase(
            project_id=project_id,
            agent_configs=agent_configs,
            description=description,
            documents=documents,
            images=images,
            analysis_plan=plan,
            clarification_answers=submission.answers,
            carryover_outputs=carryover_outputs,
            carryover_metrics=carryover_metrics,
        )
    )

    return {"status": "processing"}


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
