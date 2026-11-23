"""Graph query templates and traversal helpers for Neo4j."""

from __future__ import annotations

from typing import Any, Optional

from app.graph.neo4j_client import Neo4jClient

FIND_CALLERS = """
MATCH (caller:Function)-[:CALLS]->(target:Function)
WHERE target.name = $function_name
  AND ($repo_id IS NULL OR caller.repo_id = $repo_id)
RETURN DISTINCT caller.id AS id,
       caller.name AS name,
       caller.qualified_name AS qualified_name,
       caller.file_path AS file_path,
       caller.start_line AS start_line,
       caller.end_line AS end_line,
       caller.is_method AS is_method
ORDER BY caller.file_path, caller.start_line
"""

FIND_CALLEES = """
MATCH (source:Function {id: $function_id})-[:CALLS]->(target:Function)
RETURN DISTINCT target.id AS id,
       target.name AS name,
       target.qualified_name AS qualified_name,
       target.file_path AS file_path,
       target.start_line AS start_line,
       target.end_line AS end_line,
       target.is_method AS is_method
ORDER BY target.file_path, target.start_line
"""

TRACE_DEPENDENCIES = """
MATCH path = (source:Function {id: $function_id})-[:CALLS*1..3]->(target:Function)
RETURN [node IN nodes(path) | {
    id: node.id,
    name: node.name,
    file_path: node.file_path,
    qualified_name: node.qualified_name
}] AS path_nodes,
length(path) AS depth
ORDER BY depth ASC
"""

DELETE_REPOSITORY = """
MATCH (r:Repository {id: $repo_id})
OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
OPTIONAL MATCH (f)-[:DEFINES]->(entity)
DETACH DELETE r, f, entity
"""

GET_REPO_OVERVIEW = """
MATCH (r:Repository {id: $repo_id})
OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
RETURN r.id AS id,
       r.name AS name,
       r.root_path AS root_path,
       count(DISTINCT f) AS file_count,
       count(DISTINCT fn) AS function_count,
       count(DISTINCT c) AS class_count
"""


class GraphQueries:
    """Wrapper for executing parameterized graph queries."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def get_callers(
        self, function_name: str, repo_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        return self.client.execute_read(
            FIND_CALLERS,
            {"function_name": function_name, "repo_id": repo_id},
        )

    def get_callees(self, function_id: str) -> list[dict[str, Any]]:
        return self.client.execute_read(FIND_CALLEES, {"function_id": function_id})

    def trace_dependencies(self, function_id: str, max_depth: int = 3) -> list[dict[str, Any]]:
        # max_depth bounded between 1 and 5 to prevent combinatorial explosion
        depth = max(1, min(max_depth, 5))
        query = f"""
        MATCH path = (source:Function {{id: $function_id}})-[:CALLS*1..{depth}]->(target:Function)
        RETURN [node IN nodes(path) | {{
            id: node.id,
            name: node.name,
            file_path: node.file_path,
            qualified_name: node.qualified_name
        }}] AS path_nodes,
        length(path) AS depth
        ORDER BY depth ASC
        """
        return self.client.execute_read(query, {"function_id": function_id})

    def delete_repository(self, repo_id: str) -> None:
        self.client.execute_write(DELETE_REPOSITORY, {"repo_id": repo_id})

    def get_repository_overview(self, repo_id: str) -> Optional[dict[str, Any]]:
        res = self.client.execute_read(GET_REPO_OVERVIEW, {"repo_id": repo_id})
        return res[0] if res else None
