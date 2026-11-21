"""FastAPI routes for the RepoLens API.

All route groups are defined as separate ``APIRouter`` instances and combined at
the bottom of the module for easy mounting in ``main.py``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    CreateRepositoryRequest,
    ErrorResponse,
    GraphResponse,
    HealthResponse,
    ImpactRequest,
    ImpactResponse,
    IngestionResponse,
    RepositoryResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SymbolResponse,
)
from app.core.config import get_settings
from app.core.errors import (
    GraphError,
    IngestionError,
    LLMError,
    RepositoryNotFoundError,
    RepoLensError,
    RetrievalError,
    ValidationError,
)
from app.db.neo4j_client import get_neo4j_client, Neo4jClient
from app.embeddings.generator import EmbeddingGenerator
from app.graph.operations import GraphOperations
from app.llm.client import LLMClient
from app.retrieval.graph_retriever import GraphRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.semantic import SemanticRetriever
from app.services.chat_service import ChatService
from app.services.impact_service import ImpactService
from app.services.ingestion_service import IngestionService
from app.services.repository_service import RepositoryService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _get_db() -> Neo4jClient:
    """Return the singleton Neo4j client."""
    return get_neo4j_client()


def _graph_ops(db: Neo4jClient = Depends(_get_db)) -> GraphOperations:
    return GraphOperations(db)


def _repo_service(ops: GraphOperations = Depends(_graph_ops)) -> RepositoryService:
    return RepositoryService(ops)


def _embedding_generator() -> EmbeddingGenerator:
    settings = get_settings()
    return EmbeddingGenerator(
        model_name=settings.EMBEDDING_MODEL,
        device=settings.EMBEDDING_DEVICE,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )


def _semantic_retriever(
    ops: GraphOperations = Depends(_graph_ops),
    emb: EmbeddingGenerator = Depends(_embedding_generator),
) -> SemanticRetriever:
    return SemanticRetriever(ops, emb)


def _graph_retriever(
    ops: GraphOperations = Depends(_graph_ops),
) -> GraphRetriever:
    return GraphRetriever(ops)


def _hybrid_retriever(
    sem: SemanticRetriever = Depends(_semantic_retriever),
    gr: GraphRetriever = Depends(_graph_retriever),
) -> HybridRetriever:
    return HybridRetriever(sem, gr)


def _llm_client() -> LLMClient:
    settings = get_settings()
    return LLMClient(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )


def _ingestion_service(
    ops: GraphOperations = Depends(_graph_ops),
    emb: EmbeddingGenerator = Depends(_embedding_generator),
) -> IngestionService:
    settings = get_settings()
    return IngestionService(ops, emb, settings)


def _chat_service(
    retriever: HybridRetriever = Depends(_hybrid_retriever),
    llm: LLMClient = Depends(_llm_client),
) -> ChatService:
    return ChatService(retriever, llm)


def _impact_service(
    ops: GraphOperations = Depends(_graph_ops),
    llm: LLMClient = Depends(_llm_client),
) -> ImpactService:
    return ImpactService(ops, llm)


# ===================================================================
# Health routes
# ===================================================================

health_router = APIRouter(tags=["health"])


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic health check",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@health_router.get(
    "/health/neo4j",
    response_model=HealthResponse,
    summary="Neo4j connectivity check",
)
async def health_neo4j() -> HealthResponse:
    try:
        db = _get_db()
        await db.verify_connectivity()
        return HealthResponse(
            status="ok",
            version="0.1.0",
            details={"neo4j": "connected"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error="Neo4j unavailable", detail=str(exc)
            ).model_dump(),
        )


@health_router.get(
    "/health/llm",
    response_model=HealthResponse,
    summary="LLM availability check",
)
async def health_llm() -> HealthResponse:
    try:
        settings = get_settings()
        llm = LLMClient(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )
        available = await llm.is_available()
        if not available:
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error="LLM unavailable", detail="LLM server did not respond"
                ).model_dump(),
            )
        return HealthResponse(
            status="ok",
            version="0.1.0",
            details={"llm": "available", "model": settings.LLM_MODEL},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error="LLM check failed", detail=str(exc)
            ).model_dump(),
        )


# ===================================================================
# Repository routes
# ===================================================================

repository_router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@repository_router.post(
    "",
    response_model=RepositoryResponse,
    status_code=201,
    summary="Create a new repository",
)
async def create_repository(
    body: CreateRepositoryRequest,
    svc: RepositoryService = Depends(_repo_service),
) -> RepositoryResponse:
    try:
        repo = await svc.create(
            path=body.path, name=body.name, description=body.description
        )
        return RepositoryResponse(**repo)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RepoLensError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to create repository")
        raise HTTPException(status_code=500, detail=str(exc))


@repository_router.get(
    "",
    response_model=list[RepositoryResponse],
    summary="List all repositories",
)
async def list_repositories(
    svc: RepositoryService = Depends(_repo_service),
) -> list[RepositoryResponse]:
    try:
        repos = await svc.list_all()
        return [RepositoryResponse(**r) for r in repos]
    except Exception as exc:
        logger.exception("Failed to list repositories")
        raise HTTPException(status_code=500, detail=str(exc))


@repository_router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get repository details",
)
async def get_repository(
    repository_id: str,
    svc: RepositoryService = Depends(_repo_service),
) -> RepositoryResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        stats = await svc.get_stats(repository_id)
        repo["stats"] = stats
        return RepositoryResponse(**repo)
    except HTTPException:
        raise
    except RepositoryNotFoundError:
        raise HTTPException(status_code=404, detail="Repository not found")
    except Exception as exc:
        logger.exception("Failed to get repository %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


@repository_router.delete(
    "/{repository_id}",
    status_code=204,
    summary="Delete a repository and all its data",
)
async def delete_repository(
    repository_id: str,
    svc: RepositoryService = Depends(_repo_service),
) -> None:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        await svc.delete(repository_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete repository %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Ingestion routes
# ===================================================================

ingestion_router = APIRouter(
    prefix="/api/repositories/{repository_id}",
    tags=["ingestion"],
)


@ingestion_router.post(
    "/ingest",
    response_model=IngestionResponse,
    summary="Trigger repository ingestion",
)
async def ingest_repository(
    repository_id: str,
    svc: RepositoryService = Depends(_repo_service),
    ingestion: IngestionService = Depends(_ingestion_service),
) -> IngestionResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        result = await ingestion.ingest_repository(repository_id, repo["path"])
        return IngestionResponse(
            repo_id=result.repo_id,
            total_files=result.total_files,
            parsed_files=result.parsed_files,
            skipped_files=result.skipped_files,
            failed_files=result.failed_files,
            functions_found=result.functions_found,
            classes_found=result.classes_found,
            errors=result.errors,
            duration_seconds=result.duration_seconds,
        )
    except HTTPException:
        raise
    except IngestionError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Ingestion failed for %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


@ingestion_router.get(
    "/ingestion-status",
    summary="Get last ingestion info",
)
async def get_ingestion_status(
    repository_id: str,
    svc: RepositoryService = Depends(_repo_service),
) -> dict[str, Any]:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        stats = await svc.get_stats(repository_id)
        return {
            "repository_id": repository_id,
            "stats": stats,
            "last_ingestion": repo.get("last_ingestion"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get ingestion status for %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Search routes
# ===================================================================

search_router = APIRouter(
    prefix="/api/repositories/{repository_id}",
    tags=["search"],
)


@search_router.post(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid search over code entities",
)
async def search_code(
    repository_id: str,
    body: SearchRequest,
    svc: RepositoryService = Depends(_repo_service),
    retriever: HybridRetriever = Depends(_hybrid_retriever),
) -> SearchResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        results = await retriever.search(
            repo_id=repository_id,
            query=body.query,
            limit=body.limit,
        )

        items = [
            SearchResultItem(
                entity_id=r.entity_id,
                entity_type=r.entity_type,
                name=r.name,
                qualified_name=r.qualified_name,
                file_path=r.file_path,
                line_start=r.line_start,
                line_end=r.line_end,
                source=r.source,
                score=r.score,
                retrieval_method=r.retrieval_method,
                graph_context=r.graph_context,
                reason=r.reason,
            )
            for r in results
        ]

        # Apply entity_type filter if requested
        if body.entity_type:
            items = [
                i for i in items if i.entity_type.lower() == body.entity_type.lower()
            ]

        return SearchResponse(
            results=items,
            total=len(items),
            query=body.query,
        )
    except HTTPException:
        raise
    except RetrievalError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Search failed for repo %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Symbol routes
# ===================================================================

symbol_router = APIRouter(
    prefix="/api/repositories/{repository_id}",
    tags=["symbols"],
)


@symbol_router.get(
    "/symbols",
    response_model=list[SymbolResponse],
    summary="List symbols in a repository",
)
async def list_symbols(
    repository_id: str,
    type: str | None = Query(None, description="Filter by entity type (function, class)"),
    name: str | None = Query(None, description="Filter by name (substring match)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ops: GraphOperations = Depends(_graph_ops),
    svc: RepositoryService = Depends(_repo_service),
) -> list[SymbolResponse]:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        results = await ops.search_by_name(
            repo_id=repository_id,
            query=name or "",
            entity_type=type,
            limit=limit + offset,
        )

        # Manual offset slicing (Neo4j text search doesn't natively offset)
        page = results[offset : offset + limit]

        return [
            SymbolResponse(
                entity_id=r.get("entity_id", r.get("id", "")),
                entity_type=r.get("entity_type", r.get("type", "unknown")),
                name=r.get("name", ""),
                qualified_name=r.get("qualified_name"),
                file_path=r.get("file_path"),
                line_start=r.get("line_start"),
                line_end=r.get("line_end"),
                source=r.get("source"),
                signature=r.get("signature"),
                docstring=r.get("docstring"),
            )
            for r in page
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list symbols for repo %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


@symbol_router.get(
    "/symbols/{symbol_id:path}",
    response_model=SymbolResponse,
    summary="Get symbol details with neighbors",
)
async def get_symbol(
    repository_id: str,
    symbol_id: str,
    ops: GraphOperations = Depends(_graph_ops),
    svc: RepositoryService = Depends(_repo_service),
) -> SymbolResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        entity = await ops.get_entity(symbol_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Symbol not found")

        neighbor_data = await ops.get_neighbors(symbol_id, depth=1, limit=50)
        neighbors = [
            {**n, "relationship": n.get("relationship")}
            for n in neighbor_data.get("nodes", [])
        ]

        return SymbolResponse(
            entity_id=entity.get("entity_id", entity.get("id", symbol_id)),
            entity_type=entity.get("entity_type", entity.get("type", "unknown")),
            name=entity.get("name", ""),
            qualified_name=entity.get("qualified_name"),
            file_path=entity.get("file_path"),
            line_start=entity.get("line_start"),
            line_end=entity.get("line_end"),
            source=entity.get("source"),
            signature=entity.get("signature"),
            docstring=entity.get("docstring"),
            neighbors=neighbors,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get symbol %s", symbol_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Graph routes
# ===================================================================

graph_router = APIRouter(
    prefix="/api/repositories/{repository_id}",
    tags=["graph"],
)


@graph_router.get(
    "/graph",
    response_model=GraphResponse,
    summary="Get graph nodes and edges for visualization",
)
async def get_graph(
    repository_id: str,
    limit: int = Query(200, ge=1, le=5000),
    ops: GraphOperations = Depends(_graph_ops),
    svc: RepositoryService = Depends(_repo_service),
) -> GraphResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        data = await ops.get_repo_graph(repository_id, limit=limit)
        return GraphResponse(
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            total_nodes=len(data.get("nodes", [])),
            total_edges=len(data.get("edges", [])),
        )
    except HTTPException:
        raise
    except GraphError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to get graph for repo %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


@graph_router.get(
    "/graph/neighbors",
    response_model=GraphResponse,
    summary="Get neighbors of an entity in the graph",
)
async def get_graph_neighbors(
    repository_id: str,
    entity_id: str = Query(..., description="Entity ID to find neighbors for"),
    depth: int = Query(1, ge=1, le=5),
    limit: int = Query(50, ge=1, le=500),
    ops: GraphOperations = Depends(_graph_ops),
    svc: RepositoryService = Depends(_repo_service),
) -> GraphResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        data = await ops.get_neighbors(entity_id, depth=depth, limit=limit)
        return GraphResponse(
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            total_nodes=len(data.get("nodes", [])),
            total_edges=len(data.get("edges", [])),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get neighbors for %s", entity_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Impact routes
# ===================================================================

impact_router = APIRouter(
    prefix="/api/repositories/{repository_id}",
    tags=["impact"],
)


@impact_router.post(
    "/impact",
    response_model=ImpactResponse,
    summary="Run impact analysis on a symbol",
)
async def analyze_impact(
    repository_id: str,
    body: ImpactRequest,
    svc: RepositoryService = Depends(_repo_service),
    impact: ImpactService = Depends(_impact_service),
) -> ImpactResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        report = await impact.analyze_impact(
            repo_id=repository_id,
            entity_id_or_name=body.symbol_name,
            depth=body.depth,
        )
        return ImpactResponse(
            target=report.target_entity if isinstance(report.target_entity, dict) else {"name": str(report.target_entity)},
            direct_dependents=report.direct_dependents,
            indirect_dependents=report.indirect_dependents,
            affected_files=report.affected_files,
            dependency_paths=report.dependency_paths,
            total_impact_count=report.total_impact_count,
            summary=report.summary,
            limitations=report.limitations,
        )
    except HTTPException:
        raise
    except RepositoryNotFoundError:
        raise HTTPException(status_code=404, detail="Repository not found")
    except RepoLensError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Impact analysis failed for %s", body.symbol_name)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Chat routes
# ===================================================================

chat_router = APIRouter(
    prefix="/api/repositories/{repository_id}",
    tags=["chat"],
)


@chat_router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question about the codebase",
)
async def chat(
    repository_id: str,
    body: ChatRequest,
    svc: RepositoryService = Depends(_repo_service),
    chat_svc: ChatService = Depends(_chat_service),
) -> ChatResponse:
    try:
        repo = await svc.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        response = await chat_svc.ask(
            repo_id=repository_id,
            question=body.question,
            conversation_history=body.conversation_history,
        )
        return ChatResponse(
            answer=response.answer,
            sources=[s if isinstance(s, dict) else s.__dict__ for s in response.sources],
            retrieval_results=[
                r if isinstance(r, dict) else r.__dict__
                for r in response.retrieval_results
            ],
        )
    except HTTPException:
        raise
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM error: {exc}")
    except Exception as exc:
        logger.exception("Chat failed for repo %s", repository_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ===================================================================
# Combine all routers
# ===================================================================

all_routers: list[APIRouter] = [
    health_router,
    repository_router,
    ingestion_router,
    search_router,
    symbol_router,
    graph_router,
    impact_router,
    chat_router,
]
