"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.api.routes import router
from src.config import settings
from src.db.connection import close_client

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting application",
        environment=settings.environment.value,
        llm_provider=settings.llm_provider.value,
    )
    yield
    await close_client()
    logger.info("Shutting down application")


app = FastAPI(
    title="TFG Multi-Agent Architect",
    description="Multi-agent system for automated software architecture design",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
