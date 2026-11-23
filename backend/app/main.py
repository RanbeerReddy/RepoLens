"""RepoLens FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.repositories import router as repositories_router
from app.graph.neo4j_client import Neo4jClient
from app.llm.vllm_client import VLLMClient

app = FastAPI(
    title="RepoLens API",
    description="AI-powered codebase intelligence platform",
    version="1.0.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repositories_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic service health check."""
    return {"status": "ok", "service": "RepoLens API"}


@app.get("/health/neo4j")
def neo4j_health() -> dict[str, Any]:
    """Checks Neo4j database connectivity."""
    client = Neo4jClient()
    alive = client.ping()
    return {"status": "ok" if alive else "offline", "connected": alive}


@app.get("/health/llm")
def llm_health() -> dict[str, Any]:
    """Checks vLLM or OpenAI-compatible endpoint status."""
    client = VLLMClient()
    alive = client.ping()
    return {"status": "ok" if alive else "offline", "connected": alive}


# Serve built frontend if dist directory exists
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
