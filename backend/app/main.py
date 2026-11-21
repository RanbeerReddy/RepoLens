"""FastAPI application entry point for RepoLens."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.neo4j_client import get_neo4j_client
from app.db.schema import init_schema

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown tasks."""
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────────────────────
    setup_logging(level=settings.LOG_LEVEL)
    logger.info("Starting RepoLens API v%s", app.version)

    client = get_neo4j_client()
    await client.connect()
    await init_schema(client)

    logger.info("Startup complete")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("Shutting down RepoLens API")
    await client.close()


def create_app() -> FastAPI:
    """Build and return the configured :class:`FastAPI` application."""
    settings = get_settings()

    app = FastAPI(
        title="RepoLens API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────
    from app.api.routes import all_routers  # noqa: E402

    for r in all_routers:
        app.include_router(r)

    return app


app = create_app()
