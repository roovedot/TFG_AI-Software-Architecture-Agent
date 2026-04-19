"""MongoDB CRUD operations for projects and GridFS file storage."""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from src.db.connection import get_database, get_gridfs_bucket


async def create_project(
    description: str,
    provider: str,
    model: str,
    files_data: list[dict],
    status: str = "processing",
    markdown_content: str | None = None,
    metrics: dict | None = None,
) -> str:
    """Create a project with its files stored in GridFS.

    Args:
        files_data: list of {"name": str, "content": bytes, "content_type": str, "size": int}
        status: "processing" (default), "completed", or "error"
    """
    db = get_database()
    bucket = get_gridfs_bucket()

    # Upload files to GridFS
    file_refs = []
    for f in files_data:
        file_id = await bucket.upload_from_stream(
            f["name"],
            f["content"],
            metadata={"content_type": f["content_type"]},
        )
        file_refs.append({
            "file_id": str(file_id),
            "name": f["name"],
            "size": f["size"],
            "content_type": f["content_type"],
        })

    doc = {
        "created_at": datetime.now(timezone.utc),
        "description": description,
        "provider": provider,
        "model": model,
        "status": status,
        "error_message": None,
        "files": file_refs,
        "markdown_content": markdown_content,
        "metrics": metrics,
        "ratings": None,
        "pipeline_type": "baseline",
    }
    result = await db.projects.insert_one(doc)
    return str(result.inserted_id)


async def create_multiagent_project(
    description: str,
    agent_configs: dict,
    files_data: list[dict],
    processed_documents: list[str],
    processed_images: list[dict],
) -> str:
    """Create a multiagent project document.

    Args:
        agent_configs: {"planner": {"provider", "model"}, "requirements": ..., "designer": ..., "validator": ...}
        processed_documents: pre-extracted text from user documents (to avoid re-processing on resume)
        processed_images: pre-encoded image dicts for multimodal input
    """
    db = get_database()
    bucket = get_gridfs_bucket()

    file_refs = []
    for f in files_data:
        file_id = await bucket.upload_from_stream(
            f["name"],
            f["content"],
            metadata={"content_type": f["content_type"]},
        )
        file_refs.append({
            "file_id": str(file_id),
            "name": f["name"],
            "size": f["size"],
            "content_type": f["content_type"],
        })

    # Derive top-level provider/model for list compatibility: use planner config.
    planner_cfg = agent_configs["planner"]

    doc = {
        "created_at": datetime.now(timezone.utc),
        "description": description,
        "provider": planner_cfg["provider"],
        "model": planner_cfg["model"],
        "pipeline_type": "multiagent",
        "status": "processing",
        "current_step": "planner",
        "agent_configs": agent_configs,
        "error_message": None,
        "files": file_refs,
        "processed_documents": processed_documents,
        "processed_images": processed_images,
        "clarification_questions": None,
        "clarification_answers": None,
        "analysis_plan": None,
        "agent_outputs": {},
        "agent_metrics": [],
        "markdown_content": None,
        "metrics": None,
        "ratings": None,
    }
    result = await db.projects.insert_one(doc)
    return str(result.inserted_id)


async def update_current_step(project_id: str, step: str) -> bool:
    """Update the current_step field to reflect multiagent pipeline progress."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"current_step": step}},
    )
    return result.matched_count > 0


async def set_clarification_questions(
    project_id: str,
    questions: list[dict],
    analysis_plan: dict | None = None,
) -> bool:
    """Persist clarification questions (and the plan) and set status to waiting_clarification."""
    db = get_database()
    update_fields: dict = {
        "status": "waiting_clarification",
        "clarification_questions": questions,
        "current_step": "waiting_clarification",
    }
    if analysis_plan is not None:
        update_fields["analysis_plan"] = analysis_plan
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": update_fields},
    )
    return result.matched_count > 0


async def submit_clarification_answers(
    project_id: str, answers: dict[str, str]
) -> bool:
    """Record user's answers and flip status back to processing."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$set": {
                "clarification_answers": answers,
                "status": "processing",
                "current_step": "requirements",
            }
        },
    )
    return result.matched_count > 0


async def save_agent_output(
    project_id: str,
    agent_name: str,
    content: str,
) -> bool:
    """Save an agent's raw output to the project document."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {f"agent_outputs.{agent_name}": content}},
    )
    return result.matched_count > 0


async def save_agent_metrics(project_id: str, metrics_list: list[dict]) -> bool:
    """Overwrite the full agent_metrics array (avoids duplication from streaming)."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"agent_metrics": metrics_list}},
    )
    return result.matched_count > 0


async def complete_multiagent_project(
    project_id: str,
    markdown_content: str,
    aggregated_metrics: dict,
) -> bool:
    """Mark a multiagent project as completed with final markdown and aggregated metrics."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$set": {
                "status": "completed",
                "current_step": "completed",
                "markdown_content": markdown_content,
                "metrics": aggregated_metrics,
            }
        },
    )
    return result.matched_count > 0


async def complete_project(
    project_id: str, markdown_content: str, metrics: dict
) -> bool:
    """Mark a project as completed with its results."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$set": {
                "status": "completed",
                "markdown_content": markdown_content,
                "metrics": metrics,
            }
        },
    )
    return result.matched_count > 0


async def fail_project(project_id: str, error_message: str) -> bool:
    """Mark a project as failed with an error message."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status": "error", "error_message": error_message}},
    )
    return result.matched_count > 0


async def list_projects() -> list[dict]:
    """Return all projects as summaries, sorted by newest first."""
    db = get_database()
    cursor = db.projects.find(
        {},
        {
            "_id": 1,
            "created_at": 1,
            "description": 1,
            "provider": 1,
            "model": 1,
            "status": 1,
            "ratings": 1,
            "pipeline_type": 1,
        },
    ).sort("created_at", -1)

    projects = []
    async for doc in cursor:
        desc = doc["description"]
        projects.append({
            "id": str(doc["_id"]),
            "created_at": doc["created_at"],
            "description_preview": desc[:80] + "..." if len(desc) > 80 else desc,
            "provider": doc["provider"],
            "model": doc["model"],
            "status": doc.get("status", "completed"),
            "has_rating": doc.get("ratings") is not None,
            "pipeline_type": doc.get("pipeline_type", "baseline"),
        })
    return projects


async def get_project(project_id: str) -> dict | None:
    """Return full project data by ID."""
    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    # Ensure status field exists for older documents
    if "status" not in doc:
        doc["status"] = "completed"
    return doc


async def delete_project(project_id: str) -> bool:
    """Delete a project and its GridFS files."""
    db = get_database()
    bucket = get_gridfs_bucket()

    doc = await db.projects.find_one({"_id": ObjectId(project_id)})
    if doc is None:
        return False

    # Delete GridFS files
    for f in doc.get("files", []):
        try:
            await bucket.delete(ObjectId(f["file_id"]))
        except Exception:
            pass  # File may have already been deleted

    result = await db.projects.delete_one({"_id": ObjectId(project_id)})
    return result.deleted_count > 0


async def update_ratings(project_id: str, ratings: dict) -> bool:
    """Save or update ratings for a project."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"ratings": ratings}},
    )
    return result.matched_count > 0


async def append_chat_messages(project_id: str, messages: list[dict]) -> bool:
    """Atomically append user + assistant messages to the chat_history array."""
    db = get_database()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$push": {"chat_history": {"$each": messages}}},
    )
    return result.matched_count > 0


async def get_project_file(file_id: str) -> tuple:
    """Return a GridFS download stream and file metadata.

    Returns:
        (stream, {"name": str, "content_type": str})
    """
    bucket = get_gridfs_bucket()
    grid_out = await bucket.open_download_stream(ObjectId(file_id))
    metadata = {
        "name": grid_out.filename,
        "content_type": grid_out.metadata.get("content_type", "application/octet-stream")
        if grid_out.metadata
        else "application/octet-stream",
    }
    return grid_out, metadata
