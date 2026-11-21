"""Pydantic request/response schemas for the RepoLens API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
    version: str
    details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class CreateRepositoryRequest(BaseModel):
    """Body for POST /api/repositories."""

    path: str
    name: str | None = None
    description: str | None = None


class RepositoryResponse(BaseModel):
    """Single repository representation."""

    id: str
    name: str
    path: str
    description: str | None = None
    created_at: str | None = None
    stats: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

class IngestionResponse(BaseModel):
    """Result of a repository ingestion run."""

    repo_id: str
    total_files: int
    parsed_files: int
    skipped_files: int
    failed_files: int
    functions_found: int
    classes_found: int
    errors: list[str]
    duration_seconds: float


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Body for POST /api/repositories/{id}/search."""

    query: str
    limit: int = Field(default=10, ge=1, le=100)
    entity_type: str | None = None


class SearchResultItem(BaseModel):
    """A single search hit."""

    entity_id: str
    entity_type: str
    name: str
    qualified_name: str | None = None
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    source: str | None = None
    score: float | None = None
    retrieval_method: str | None = None
    graph_context: str | None = None
    reason: str | None = None


class SearchResponse(BaseModel):
    """Wrapper around a list of search results."""

    results: list[SearchResultItem]
    total: int
    query: str


# ---------------------------------------------------------------------------
# Symbol
# ---------------------------------------------------------------------------

class SymbolResponse(BaseModel):
    """Details for a single code symbol (function, class, etc.)."""

    entity_id: str
    entity_type: str
    name: str
    qualified_name: str | None = None
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    source: str | None = None
    signature: str | None = None
    docstring: str | None = None
    neighbors: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class GraphResponse(BaseModel):
    """Nodes and edges for the graph visualizer."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    total_nodes: int
    total_edges: int


# ---------------------------------------------------------------------------
# Impact
# ---------------------------------------------------------------------------

class ImpactRequest(BaseModel):
    """Body for POST /api/repositories/{id}/impact."""

    symbol_name: str
    depth: int = Field(default=3, ge=1, le=10)


class ImpactResponse(BaseModel):
    """Impact-analysis results."""

    target: dict[str, Any]
    direct_dependents: list[dict[str, Any]]
    indirect_dependents: list[dict[str, Any]]
    affected_files: list[str]
    dependency_paths: list[list[dict[str, Any]]]
    total_impact_count: int
    summary: str | None = None
    limitations: list[str] | None = None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Body for POST /api/repositories/{id}/chat."""

    question: str
    conversation_history: list[dict[str, Any]] | None = None


class ChatResponse(BaseModel):
    """Chat answer with provenance."""

    answer: str
    sources: list[dict[str, Any]]
    retrieval_results: list[dict[str, Any]]
