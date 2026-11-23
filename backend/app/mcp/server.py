"""RepoLens Model Context Protocol (MCP) Server.

Exposes codebase intelligence, hybrid retrieval, symbol lookup, dependency tracing,
and change impact analysis to external AI assistants (Claude Desktop, Cursor, etc.).
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from app.graph.neo4j_client import Neo4jClient
from app.graph.queries import GraphQueries
from app.retrieval.hybrid_search import HybridSearchEngine
from app.services.impact_service import ImpactService

LIST_REPOS_QUERY = """
MATCH (r:Repository)
RETURN r.id AS id,
       r.name AS name,
       r.root_path AS root_path,
       r.total_files AS total_files,
       r.total_functions AS total_functions,
       r.total_classes AS total_classes,
       r.total_lines AS total_lines
ORDER BY r.name
"""

GET_SYMBOL_QUERY = """
MATCH (fn:Function)
WHERE (fn.name = $name OR fn.qualified_name = $name OR fn.id = $name)
  AND ($repo_id IS NULL OR fn.repo_id = $repo_id)
OPTIONAL MATCH (caller:Function)-[:CALLS]->(fn)
OPTIONAL MATCH (fn)-[:CALLS]->(callee:Function)
RETURN fn.id AS id,
       fn.name AS name,
       fn.qualified_name AS qualified_name,
       fn.file_path AS file_path,
       fn.start_line AS start_line,
       fn.end_line AS end_line,
       fn.signature AS signature,
       fn.docstring AS docstring,
       fn.source AS source,
       fn.is_method AS is_method,
       collect(DISTINCT caller.name) AS callers,
       collect(DISTINCT callee.name) AS callees
LIMIT 1
"""

EXPLAIN_ARCH_QUERY = """
MATCH (r:Repository)
WHERE ($repo_id IS NULL OR r.id = $repo_id)
OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
RETURN r.id AS repo_id,
       r.name AS repo_name,
       r.root_path AS root_path,
       count(DISTINCT f) AS file_count,
       count(DISTINCT fn) AS function_count,
       count(DISTINCT c) AS class_count,
       collect(DISTINCT f.path)[0..10] AS sample_files
LIMIT 1
"""


def create_mcp_server(
    neo4j_client: Optional[Neo4jClient] = None,
    hybrid_engine: Optional[HybridSearchEngine] = None,
    impact_svc: Optional[ImpactService] = None,
) -> FastMCP:
    """Factory creating configured FastMCP server instance."""
    server = FastMCP(
        "repolens",
        instructions="RepoLens AI Codebase Intelligence MCP Server",
    )

    client = neo4j_client or Neo4jClient()
    hybrid = hybrid_engine or HybridSearchEngine(client=client)
    impact = impact_svc or ImpactService(neo4j_client=client)
    queries = GraphQueries(client)

    @server.tool()
    def list_repositories() -> list[dict[str, Any]]:
        """List all repositories currently registered and indexed in RepoLens."""
        if not client.ping():
            return [{"status": "Neo4j database offline"}]
        return client.execute_read(LIST_REPOS_QUERY)

    @server.tool()
    def search_code(
        query: str,
        repo_id: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search codebase using hybrid retrieval (semantic, keyword, and graph).
        Returns matching symbols with verified file paths, line ranges, and source code.
        """
        results = hybrid.search(query=query, limit=limit, repo_id=repo_id)
        return [
            {
                "name": r.name,
                "qualified_name": r.qualified_name,
                "file_path": r.file_path,
                "lines": f"{r.start_line}-{r.end_line}",
                "signature": r.signature,
                "docstring": r.docstring,
                "relevance_score": r.final_score,
                "retrieval_reasons": r.reasons,
                "source": r.source,
            }
            for r in results
        ]

    @server.tool()
    def get_symbol(
        symbol_name: str,
        repo_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Retrieve complete symbol details (signature, docstring, source, callers, callees).
        """
        if not client.ping():
            return {"error": "Neo4j database offline"}
        records = client.execute_read(
            GET_SYMBOL_QUERY,
            {"name": symbol_name, "repo_id": repo_id},
        )
        if not records:
            return {"error": f"Symbol '{symbol_name}' not found."}
        return records[0]

    @server.tool()
    def trace_dependencies(
        symbol_name: str,
        depth: int = 2,
        repo_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Trace direct callers, callees, and multi-hop dependency execution paths for a function.
        """
        callers = queries.get_callers(symbol_name, repo_id=repo_id)
        callees = queries.get_callees(symbol_name)
        paths = queries.trace_dependencies(symbol_name, max_depth=depth)
        return {
            "symbol": symbol_name,
            "callers": callers,
            "callees": callees,
            "paths": paths,
        }

    @server.tool()
    def impact_analysis(
        function_name: str,
        repo_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run static change impact analysis to assess breakages before modifying a function.
        Returns impact level (LOW/MEDIUM/HIGH), dependents, affected files, tests, and summary.
        """
        report = impact.analyze_impact(function_name, repo_id=repo_id)
        return report.model_dump()

    @server.tool()
    def explain_architecture(repo_id: Optional[str] = None) -> dict[str, Any]:
        """
        Summarize repository topology: total files, functions, classes, and top module samples.
        """
        if not client.ping():
            return {"error": "Neo4j database offline"}
        records = client.execute_read(EXPLAIN_ARCH_QUERY, {"repo_id": repo_id})
        return records[0] if records else {"error": "No architecture data available"}

    return server


mcp = create_mcp_server()

if __name__ == "__main__":
    mcp.run()
