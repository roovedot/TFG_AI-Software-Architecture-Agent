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
    markdown_content: str,
    metrics: dict,
) -> str:
    """Create a project with its files stored in GridFS.

    Args:
        files_data: list of {"name": str, "content": bytes, "content_type": str, "size": int}
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
        "files": file_refs,
        "markdown_content": markdown_content,
        "metrics": metrics,
        "ratings": None,
    }
    result = await db.projects.insert_one(doc)
    return str(result.inserted_id)


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
            "ratings": 1,
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
            "has_rating": doc.get("ratings") is not None,
        })
    return projects


async def get_project(project_id: str) -> dict | None:
    """Return full project data by ID."""
    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
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
