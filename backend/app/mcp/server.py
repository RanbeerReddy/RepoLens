"""Model Context Protocol (MCP) server for RepoLens.

Exposes RepoLens code intelligence tools to external AI clients such as Claude Desktop,
Cursor, or any other MCP-compatible client.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.config import get_settings
from app.db.neo4j_client import get_neo4j_client
from app.embeddings.generator import EmbeddingGenerator
from app.graph.operations import GraphOperations
from app.retrieval.graph_retriever import GraphRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.semantic import SemanticRetriever
from app.services.impact_service import ImpactService
from app.services.repository_service import RepositoryService

logger = logging.getLogger("repolens.mcp")

# Initialize FastMCP Server
mcp = FastMCP("RepoLens Code Intelligence")


def _get_services():
    """Helper to initialize the shared backend services."""
    settings = get_settings()
    db = get_neo4j_client()
    graph_ops = GraphOperations(db)
    repo_service = RepositoryService(graph_ops)

    embedding_gen = EmbeddingGenerator(
        model_name=settings.EMBEDDING_MODEL,
        device=settings.EMBEDDING_DEVICE,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )
    semantic_retriever = SemanticRetriever(graph_ops, embedding_gen)
    graph_retriever = GraphRetriever(graph_ops)
    hybrid_retriever = HybridRetriever(semantic_retriever, graph_retriever)
    impact_service = ImpactService(graph_ops)

    return repo_service, hybrid_retriever, impact_service, graph_ops


@mcp.tool()
async def list_repositories() -> str:
    """Return all repositories currently registered in RepoLens."""
    try:
        repo_service, _, _, _ = _get_services()
        repos = await repo_service.list_all()
        return json.dumps(repos, indent=2)
    except Exception as exc:
        logger.exception("MCP list_repositories error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def search_code(repository_id: str, query: str, limit: int = 10) -> str:
    """Search repository code using hybrid (semantic + graph + lexical) retrieval.

    Args:
        repository_id: The ID of the repository to search.
        query: Natural language or keyword code query.
        limit: Maximum number of results to return (default 10).
    """
    try:
        _, hybrid_retriever, _, _ = _get_services()
        results = await hybrid_retriever.search(
            repo_id=repository_id,
            query=query,
            limit=limit,
        )
        data = [
            r.model_dump() if hasattr(r, "model_dump") else r.__dict__
            for r in results
        ]
        return json.dumps(data, indent=2)
    except Exception as exc:
        logger.exception("MCP search_code error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def get_symbol(
    repository_id: str, symbol_name: str, file_path: str | None = None
) -> str:
    """Retrieve details, docstrings, source code, and relationships for a function, class, or module.

    Args:
        repository_id: Target repository ID.
        symbol_name: The name or qualified name of the symbol.
        file_path: Optional relative file path to narrow down matches.
    """
    try:
        _, _, _, graph_ops = _get_services()
        matches = await graph_ops.search_by_name(
            repo_id=repository_id,
            query=symbol_name,
            limit=10,
        )
        if file_path:
            matches = [m for m in matches if m.get("file_path") == file_path]

        if not matches:
            return json.dumps({"message": f"Symbol '{symbol_name}' not found in repo {repository_id}"})

        return json.dumps(matches, indent=2)
    except Exception as exc:
        logger.exception("MCP get_symbol error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def trace_dependencies(
    repository_id: str,
    symbol_name: str,
    direction: str = "both",
    depth: int = 2,
) -> str:
    """Trace callers and callees for a function or class.

    Args:
        repository_id: Target repository ID.
        symbol_name: Name or entity ID of the target symbol.
        direction: 'callers', 'callees', or 'both'.
        depth: Traversal depth (default 2).
    """
    try:
        _, _, _, graph_ops = _get_services()
        entity = await graph_ops.get_entity(symbol_name)
        if not entity:
            matches = await graph_ops.search_by_name(repo_id=repository_id, query=symbol_name, limit=1)
            if matches:
                entity = matches[0]

        if not entity:
            return json.dumps({"error": f"Symbol '{symbol_name}' not found."})

        entity_id = entity["id"]
        results: dict[str, Any] = {"target": entity}

        if direction in ("callers", "both"):
            results["callers"] = await graph_ops.get_callers(entity_id, depth=depth)
        if direction in ("callees", "both"):
            results["callees"] = await graph_ops.get_callees(entity_id, depth=depth)

        return json.dumps(results, indent=2)
    except Exception as exc:
        logger.exception("MCP trace_dependencies error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def impact_analysis(
    repository_id: str,
    symbol_name: str,
    depth: int = 3,
) -> str:
    """Analyze the blast radius and affected files if a function or class is modified.

    Args:
        repository_id: Target repository ID.
        symbol_name: The name or entity ID of the symbol to analyze.
        depth: Graph traversal depth (default 3).
    """
    try:
        _, _, impact_svc, _ = _get_services()
        report = await impact_svc.analyze_impact(
            repo_id=repository_id,
            entity_id_or_name=symbol_name,
            depth=depth,
        )
        return json.dumps(
            report.model_dump() if hasattr(report, "model_dump") else report.__dict__,
            indent=2,
        )
    except Exception as exc:
        logger.exception("MCP impact_analysis error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def explain_architecture(repository_id: str) -> str:
    """Generate an overview of repository structure, key modules, and graph topology.

    Args:
        repository_id: Target repository ID.
    """
    try:
        repo_svc, _, _, graph_ops = _get_services()
        repo = await repo_svc.get(repository_id)
        if not repo:
            return json.dumps({"error": "Repository not found"})

        stats = await repo_svc.get_stats(repository_id)
        graph = await graph_ops.get_repo_graph(repository_id, limit=100)

        overview = {
            "repository": repo,
            "statistics": stats,
            "key_nodes_sample": graph.get("nodes", [])[:20],
            "relationships_count": len(graph.get("edges", [])),
        }
        return json.dumps(overview, indent=2)
    except Exception as exc:
        logger.exception("MCP explain_architecture error: %s", exc)
        return json.dumps({"error": str(exc)})


def run_server():
    """Run the MCP server over standard I/O (default for desktop clients)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
