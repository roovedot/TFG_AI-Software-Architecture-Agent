"""MongoDB client singleton and GridFS bucket."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket

from src.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_database]


def get_gridfs_bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(get_database())


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
