"""Neo4j graph operations for RepoLens."""

from __future__ import annotations

import logging
from typing import Any

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphOperations:
    """High-level async operations against the Neo4j code graph."""

    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    # ------------------------------------------------------------------ #
    #  CREATE operations (MERGE for idempotency)
    # ------------------------------------------------------------------ #

    async def create_repository(
        self,
        repo_id: str,
        name: str,
        path: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        query = """
        MERGE (r:Repository {id: $repo_id})
        ON CREATE SET
            r.name        = $name,
            r.path        = $path,
            r.description = $description,
            r.created_at  = datetime()
        ON MATCH SET
            r.name        = $name,
            r.path        = $path,
            r.description = $description,
            r.updated_at  = datetime()
        RETURN r {.*} AS repo
        """
        result = await self._client.execute_write(
            query,
            {
                "repo_id": repo_id,
                "name": name,
                "path": path,
                "description": description,
            },
        )
        return result[0]["repo"] if result else {}

    async def create_file(
        self,
        repo_id: str,
        file_path: str,
        relative_path: str,
        source_hash: str,
        size_bytes: int,
        last_modified: str,
    ) -> dict[str, Any]:
        query = """
        MERGE (f:File {id: $file_id})
        ON CREATE SET
            f.path          = $file_path,
            f.relative_path = $relative_path,
            f.repo_id       = $repo_id,
            f.source_hash   = $source_hash,
            f.size_bytes    = $size_bytes,
            f.last_modified = $last_modified,
            f.created_at    = datetime()
        ON MATCH SET
            f.path          = $file_path,
            f.relative_path = $relative_path,
            f.source_hash   = $source_hash,
            f.size_bytes    = $size_bytes,
            f.last_modified = $last_modified,
            f.updated_at    = datetime()
        WITH f
        MATCH (r:Repository {id: $repo_id})
        MERGE (r)-[:CONTAINS]->(f)
        RETURN f {.*} AS file
        """
        file_id = f"{repo_id}:{file_path}"
        result = await self._client.execute_write(
            query,
            {
                "file_id": file_id,
                "file_path": file_path,
                "relative_path": relative_path,
                "repo_id": repo_id,
                "source_hash": source_hash,
                "size_bytes": size_bytes,
                "last_modified": last_modified,
            },
        )
        return result[0]["file"] if result else {}

    async def create_function(
        self,
        entity_id: str,
        name: str,
        qualified_name: str,
        file_path: str,
        repo_id: str,
        line_start: int,
        line_end: int,
        source: str,
        signature: str,
        docstring: str | None,
        is_method: bool,
        is_async: bool,
        decorators: list[str],
        args: list[str],
    ) -> dict[str, Any]:
        query = """
        MERGE (fn:Function {id: $entity_id})
        ON CREATE SET
            fn.name           = $name,
            fn.qualified_name = $qualified_name,
            fn.file_path      = $file_path,
            fn.repo_id        = $repo_id,
            fn.line_start     = $line_start,
            fn.line_end       = $line_end,
            fn.source         = $source,
            fn.signature      = $signature,
            fn.docstring      = $docstring,
            fn.is_method      = $is_method,
            fn.is_async       = $is_async,
            fn.decorators     = $decorators,
            fn.args           = $args,
            fn.entity_type    = 'function',
            fn.created_at     = datetime()
        ON MATCH SET
            fn.name           = $name,
            fn.qualified_name = $qualified_name,
            fn.file_path      = $file_path,
            fn.line_start     = $line_start,
            fn.line_end       = $line_end,
            fn.source         = $source,
            fn.signature      = $signature,
            fn.docstring      = $docstring,
            fn.is_method      = $is_method,
            fn.is_async       = $is_async,
            fn.decorators     = $decorators,
            fn.args           = $args,
            fn.updated_at     = datetime()
        WITH fn
        MATCH (f:File {id: $file_id})
        MERGE (f)-[:DEFINES]->(fn)
        RETURN fn {.*} AS func
        """
        file_id = f"{repo_id}:{file_path}"
        result = await self._client.execute_write(
            query,
            {
                "entity_id": entity_id,
                "name": name,
                "qualified_name": qualified_name,
                "file_path": file_path,
                "repo_id": repo_id,
                "line_start": line_start,
                "line_end": line_end,
                "source": source,
                "signature": signature,
                "docstring": docstring,
                "is_method": is_method,
                "is_async": is_async,
                "decorators": decorators,
                "args": args,
                "file_id": file_id,
            },
        )
        return result[0]["func"] if result else {}

    async def create_class(
        self,
        entity_id: str,
        name: str,
        qualified_name: str,
        file_path: str,
        repo_id: str,
        line_start: int,
        line_end: int,
        source: str,
        docstring: str | None,
        decorators: list[str],
        bases: list[str],
    ) -> dict[str, Any]:
        query = """
        MERGE (cls:Class {id: $entity_id})
        ON CREATE SET
            cls.name           = $name,
            cls.qualified_name = $qualified_name,
            cls.file_path      = $file_path,
            cls.repo_id        = $repo_id,
            cls.line_start     = $line_start,
            cls.line_end       = $line_end,
            cls.source         = $source,
            cls.docstring      = $docstring,
            cls.decorators     = $decorators,
            cls.bases          = $bases,
            cls.entity_type    = 'class',
            cls.created_at     = datetime()
        ON MATCH SET
            cls.name           = $name,
            cls.qualified_name = $qualified_name,
            cls.file_path      = $file_path,
            cls.line_start     = $line_start,
            cls.line_end       = $line_end,
            cls.source         = $source,
            cls.docstring      = $docstring,
            cls.decorators     = $decorators,
            cls.bases          = $bases,
            cls.updated_at     = datetime()
        WITH cls
        MATCH (f:File {id: $file_id})
        MERGE (f)-[:DEFINES]->(cls)
        RETURN cls {.*} AS class_node
        """
        file_id = f"{repo_id}:{file_path}"
        result = await self._client.execute_write(
            query,
            {
                "entity_id": entity_id,
                "name": name,
                "qualified_name": qualified_name,
                "file_path": file_path,
                "repo_id": repo_id,
                "line_start": line_start,
                "line_end": line_end,
                "source": source,
                "docstring": docstring,
                "decorators": decorators,
                "bases": bases,
                "file_id": file_id,
            },
        )
        return result[0]["class_node"] if result else {}

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        # Whitelist valid relationship types to prevent injection via rel_type
        valid_rel_types = {
            "CALLS",
            "IMPORTS",
            "INHERITS",
            "CONTAINS",
            "DEFINES",
            "HAS_METHOD",
            "DEPENDS_ON",
            "USES",
        }
        if rel_type not in valid_rel_types:
            logger.warning("Invalid relationship type: %s", rel_type)
            return False

        props_clause = ""
        params: dict[str, Any] = {"from_id": from_id, "to_id": to_id}
        if properties:
            prop_assignments = ", ".join(
                f"rel.{key} = $prop_{key}" for key in properties
            )
            props_clause = f"ON CREATE SET {prop_assignments} ON MATCH SET {prop_assignments}"
            for key, value in properties.items():
                params[f"prop_{key}"] = value

        # rel_type is from a trusted whitelist, safe to interpolate
        query = f"""
        MATCH (a {{id: $from_id}})
        MATCH (b {{id: $to_id}})
        MERGE (a)-[rel:{rel_type}]->(b)
        {props_clause}
        RETURN type(rel) AS rtype
        """
        result = await self._client.execute_write(query, params)
        return len(result) > 0

    # ------------------------------------------------------------------ #
    #  DELETE / REMOVE
    # ------------------------------------------------------------------ #

    async def remove_file_entities(self, repo_id: str, file_path: str) -> None:
        """Remove all entities (functions, classes) belonging to a file."""
        query = """
        MATCH (f:File {id: $file_id})
        OPTIONAL MATCH (f)-[:DEFINES]->(e)
        DETACH DELETE e
        WITH f
        DETACH DELETE f
        """
        file_id = f"{repo_id}:{file_path}"
        await self._client.execute_write(query, {"file_id": file_id})

    async def delete_repository(self, repo_id: str) -> None:
        """Delete a repository and ALL related nodes/relationships."""
        query = """
        MATCH (r:Repository {id: $repo_id})
        OPTIONAL MATCH (r)-[*]->(n)
        DETACH DELETE n, r
        """
        await self._client.execute_write(query, {"repo_id": repo_id})

    # ------------------------------------------------------------------ #
    #  READ operations
    # ------------------------------------------------------------------ #

    async def get_repository(self, repo_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (r:Repository {id: $repo_id})
        RETURN r {.*} AS repo
        """
        result = await self._client.execute_read(query, {"repo_id": repo_id})
        return result[0]["repo"] if result else None

    async def list_repositories(self) -> list[dict[str, Any]]:
        query = """
        MATCH (r:Repository)
        RETURN r {.*} AS repo
        ORDER BY r.name
        """
        result = await self._client.execute_read(query, {})
        return [row["repo"] for row in result]

    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (e {id: $entity_id})
        RETURN e {.*,  labels: labels(e)} AS entity
        """
        result = await self._client.execute_read(
            query, {"entity_id": entity_id}
        )
        return result[0]["entity"] if result else None

    async def get_file_entities(
        self, repo_id: str, file_path: str
    ) -> list[dict[str, Any]]:
        query = """
        MATCH (f:File {id: $file_id})-[:DEFINES]->(e)
        RETURN e {.*, labels: labels(e)} AS entity
        ORDER BY e.line_start
        """
        file_id = f"{repo_id}:{file_path}"
        result = await self._client.execute_read(query, {"file_id": file_id})
        return [row["entity"] for row in result]

    async def get_neighbors(
        self, entity_id: str, depth: int = 1, limit: int = 50
    ) -> dict[str, Any]:
        query = """
        MATCH (start {id: $entity_id})
        CALL apoc.path.subgraphAll(start, {maxLevel: $depth, limit: $limit})
        YIELD nodes, relationships
        RETURN
            [n IN nodes | n {.*, labels: labels(n)}] AS nodes,
            [r IN relationships |
                {source: startNode(r).id, target: endNode(r).id,
                 type: type(r), properties: properties(r)}
            ] AS edges
        """
        # Fallback for environments without APOC
        fallback_query = """
        MATCH path = (start {id: $entity_id})-[*1..""" + str(min(depth, 5)) + """]->(neighbor)
        WITH start, collect(DISTINCT neighbor) AS neighbors,
             collect(DISTINCT relationships(path)) AS all_rels
        WITH start,
             neighbors,
             reduce(acc = [], rels IN all_rels | acc + rels) AS flat_rels
        WITH [start] + neighbors AS all_nodes,
             apoc.coll.toSet(flat_rels) AS unique_rels
        RETURN
            [n IN all_nodes | n {.*, labels: labels(n)}][0..$limit] AS nodes,
            [r IN unique_rels |
                {source: startNode(r).id, target: endNode(r).id,
                 type: type(r), properties: properties(r)}
            ] AS edges
        """
        # Use a simpler query that works without APOC
        simple_query = f"""
        MATCH (start {{id: $entity_id}})
        OPTIONAL MATCH path = (start)-[*1..{min(depth, 5)}]-(neighbor)
        WITH start,
             collect(DISTINCT neighbor) AS neighbors,
             collect(DISTINCT last(relationships(path))) AS rels
        WITH [start] + neighbors AS all_nodes, rels
        UNWIND all_nodes AS n
        WITH collect(DISTINCT n {{.*, labels: labels(n)}})[0..$limit] AS nodes, rels
        RETURN
            nodes,
            [r IN rels WHERE r IS NOT NULL |
                {{source: startNode(r).id, target: endNode(r).id,
                 type: type(r)}}
            ] AS edges
        """
        try:
            result = await self._client.execute_read(
                simple_query,
                {"entity_id": entity_id, "limit": limit},
            )
        except Exception:
            logger.debug("Neighbor query failed, returning empty result")
            return {"nodes": [], "edges": []}

        if result:
            return {
                "nodes": result[0]["nodes"],
                "edges": result[0]["edges"],
            }
        return {"nodes": [], "edges": []}

    async def get_repo_stats(self, repo_id: str) -> dict[str, Any]:
        query = """
        OPTIONAL MATCH (f:File {repo_id: $repo_id})
        WITH count(DISTINCT f) AS file_count
        OPTIONAL MATCH (fn:Function {repo_id: $repo_id})
        WITH file_count, count(DISTINCT fn) AS function_count
        OPTIONAL MATCH (cls:Class {repo_id: $repo_id})
        WITH file_count, function_count, count(DISTINCT cls) AS class_count
        OPTIONAL MATCH (a {repo_id: $repo_id})-[rel]->(b {repo_id: $repo_id})
        RETURN
            file_count     AS files,
            function_count AS functions,
            class_count    AS classes,
            count(rel)     AS relationships
        """
        result = await self._client.execute_read(
            query, {"repo_id": repo_id}
        )
        if result:
            row = result[0]
            return {
                "files": row["files"],
                "functions": row["functions"],
                "classes": row["classes"],
                "relationships": row["relationships"],
            }
        return {"files": 0, "functions": 0, "classes": 0, "relationships": 0}

    async def search_by_name(
        self,
        repo_id: str,
        query_str: str,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        label_filter = ""
        if entity_type and entity_type.lower() in ("function", "class", "file"):
            label_filter = f"AND e:{entity_type.capitalize()}"

        query = f"""
        MATCH (e {{repo_id: $repo_id}})
        WHERE (e:Function OR e:Class OR e:File)
              {label_filter}
              AND toLower(e.name) CONTAINS toLower($query)
        RETURN e {{.*, labels: labels(e)}} AS entity
        ORDER BY
            CASE WHEN toLower(e.name) = toLower($query) THEN 0
                 WHEN toLower(e.name) STARTS WITH toLower($query) THEN 1
                 ELSE 2
            END,
            e.name
        LIMIT $limit
        """
        result = await self._client.execute_read(
            query,
            {"repo_id": repo_id, "query": query_str, "limit": limit},
        )
        return [row["entity"] for row in result]

    async def get_callers(
        self, entity_id: str, depth: int = 1
    ) -> list[dict[str, Any]]:
        query = f"""
        MATCH (target {{id: $entity_id}})
        MATCH (caller)-[:CALLS*1..{min(depth, 5)}]->(target)
        RETURN DISTINCT caller {{.*, labels: labels(caller)}} AS entity
        """
        result = await self._client.execute_read(
            query, {"entity_id": entity_id}
        )
        return [row["entity"] for row in result]

    async def get_callees(
        self, entity_id: str, depth: int = 1
    ) -> list[dict[str, Any]]:
        query = f"""
        MATCH (source {{id: $entity_id}})
        MATCH (source)-[:CALLS*1..{min(depth, 5)}]->(callee)
        RETURN DISTINCT callee {{.*, labels: labels(callee)}} AS entity
        """
        result = await self._client.execute_read(
            query, {"entity_id": entity_id}
        )
        return [row["entity"] for row in result]

    async def get_dependency_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        query = f"""
        MATCH path = shortestPath(
            (a {{id: $from_id}})-[*1..{min(max_depth, 10)}]-(b {{id: $to_id}})
        )
        UNWIND nodes(path) AS n
        RETURN n {{.*, labels: labels(n)}} AS entity
        """
        result = await self._client.execute_read(
            query, {"from_id": from_id, "to_id": to_id}
        )
        return [row["entity"] for row in result]

    async def get_repo_graph(
        self, repo_id: str, limit: int = 200
    ) -> dict[str, Any]:
        query = """
        MATCH (n {repo_id: $repo_id})
        WHERE n:File OR n:Function OR n:Class
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]->(m {repo_id: $repo_id})
        WHERE m:File OR m:Function OR m:Class
        RETURN
            collect(DISTINCT n {.*, labels: labels(n)}) AS nodes,
            collect(DISTINCT {
                source: n.id,
                target: m.id,
                type: type(r)
            }) AS edges
        """
        result = await self._client.execute_read(
            query, {"repo_id": repo_id, "limit": limit}
        )
        if result:
            # Filter out edges where target is null (from OPTIONAL MATCH)
            edges = [
                e for e in result[0]["edges"]
                if e.get("target") is not None
            ]
            return {"nodes": result[0]["nodes"], "edges": edges}
        return {"nodes": [], "edges": []}

    # ------------------------------------------------------------------ #
    #  Embedding / Vector operations
    # ------------------------------------------------------------------ #

    async def update_embedding(
        self, entity_id: str, embedding: list[float]
    ) -> None:
        query = """
        MATCH (e {id: $entity_id})
        SET e.embedding = $embedding
        """
        await self._client.execute_write(
            query, {"entity_id": entity_id, "embedding": embedding}
        )

    async def vector_search(
        self,
        repo_id: str,
        embedding: list[float],
        limit: int = 10,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search entities by vector similarity using cosine distance.

        Attempts to use the native Neo4j vector index first, falling back to a
        brute-force cosine similarity computation when the index is unavailable.
        """
        # Try native vector index first
        label = "Function"
        if entity_type and entity_type.lower() in ("class",):
            label = "Class"

        native_query = f"""
        CALL db.index.vector.queryNodes('{label.lower()}_embedding_index', $limit, $embedding)
        YIELD node, score
        WHERE node.repo_id = $repo_id
        RETURN node {{.*, labels: labels(node), score: score}} AS entity
        LIMIT $limit
        """

        try:
            result = await self._client.execute_read(
                native_query,
                {
                    "repo_id": repo_id,
                    "embedding": embedding,
                    "limit": limit,
                },
            )
            return [row["entity"] for row in result]
        except Exception:
            logger.debug(
                "Native vector index not available, using brute-force search"
            )

        # Brute-force fallback: compute cosine similarity manually
        label_filter = ""
        if entity_type and entity_type.lower() in ("function", "class", "file"):
            label_filter = f"AND e:{entity_type.capitalize()}"

        fallback_query = f"""
        MATCH (e {{repo_id: $repo_id}})
        WHERE (e:Function OR e:Class)
              {label_filter}
              AND e.embedding IS NOT NULL
        WITH e,
             reduce(dot = 0.0, i IN range(0, size(e.embedding)-1) |
                 dot + e.embedding[i] * $embedding[i]) AS dot_product,
             reduce(norm_a = 0.0, x IN e.embedding | norm_a + x * x) AS norm_a_sq,
             reduce(norm_b = 0.0, x IN $embedding | norm_b + x * x) AS norm_b_sq
        WITH e, dot_product / (sqrt(norm_a_sq) * sqrt(norm_b_sq) + 1e-10) AS score
        ORDER BY score DESC
        LIMIT $limit
        RETURN e {{.*, labels: labels(e), score: score}} AS entity
        """
        result = await self._client.execute_read(
            fallback_query,
            {
                "repo_id": repo_id,
                "embedding": embedding,
                "limit": limit,
            },
        )
        return [row["entity"] for row in result]
