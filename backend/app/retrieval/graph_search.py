"""Graph neighborhood retrieval engine."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.graph.neo4j_client import Neo4jClient

GRAPH_NEIGHBORS_QUERY = """
MATCH (fn:Function {id: $func_id})
OPTIONAL MATCH (caller:Function)-[:CALLS]->(fn)
OPTIONAL MATCH (fn)-[:CALLS]->(callee:Function)
RETURN fn.id AS id,
       collect(DISTINCT {name: caller.name, file: caller.file_path, id: caller.id}) AS callers,
       collect(DISTINCT {name: callee.name, file: callee.file_path, id: callee.id}) AS callees
"""


class GraphNeighbors(BaseModel):
    """Structural neighborhood context for a function."""

    function_id: str
    callers: list[dict[str, str]] = Field(default_factory=list)
    callees: list[dict[str, str]] = Field(default_factory=list)
    graph_relevance: float = 0.0
    relationship_summary: list[str] = Field(default_factory=list)


class GraphSearchEngine:
    """Enriches candidate entities with graph dependency topology."""

    def __init__(self, client: Optional[Neo4jClient] = None) -> None:
        self.client = client

    def get_neighborhood(self, function_id: str) -> GraphNeighbors:
        """Retrieves 1-hop callers and callees from Neo4j."""
        if not self.client:
            return GraphNeighbors(function_id=function_id)

        records = self.client.execute_read(
            GRAPH_NEIGHBORS_QUERY,
            {"func_id": function_id},
        )
        if not records:
            return GraphNeighbors(function_id=function_id)

        data = records[0]
        callers = [c for c in data.get("callers", []) if c.get("id")]
        callees = [c for c in data.get("callees", []) if c.get("id")]

        summaries: list[str] = []
        if callers:
            c_names = ", ".join(c["name"] for c in callers[:3])
            summaries.append(f"Called by: {c_names}")
        if callees:
            c_names = ", ".join(c["name"] for c in callees[:3])
            summaries.append(f"Calls: {c_names}")

        relevance = min(1.0, 0.3 * len(callers) + 0.2 * len(callees))

        return GraphNeighbors(
            function_id=function_id,
            callers=callers,
            callees=callees,
            graph_relevance=relevance,
            relationship_summary=summaries,
        )

    @staticmethod
    def get_neighborhood_in_memory(
        function_id: str,
        calls_graph: dict[str, list[str]],  # caller_id -> list of callee names or ids
        candidates_by_name: dict[str, str],  # name -> id
    ) -> GraphNeighbors:
        """In-memory graph neighborhood expansion for unit testing and offline mode."""
        # Find callees
        callee_names = calls_graph.get(function_id, [])
        callees = [{"name": name, "id": candidates_by_name.get(name, "")} for name in callee_names]

        # Find callers
        callers: list[dict[str, str]] = []
        for src_id, target_names in calls_graph.items():
            if any(name in function_id for name in target_names):
                callers.append({"name": src_id.split(":")[-1], "id": src_id})

        summaries: list[str] = []
        if callers:
            summaries.append(f"Called by: {', '.join(c['name'] for c in callers[:3])}")
        if callees:
            summaries.append(f"Calls: {', '.join(c['name'] for c in callees[:3])}")

        relevance = min(1.0, 0.3 * len(callers) + 0.2 * len(callees))

        return GraphNeighbors(
            function_id=function_id,
            callers=callers,
            callees=callees,
            graph_relevance=relevance,
            relationship_summary=summaries,
        )
