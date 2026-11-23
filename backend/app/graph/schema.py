"""Neo4j graph schema constraints, indexes, and vector indexes."""

from __future__ import annotations

from app.graph.neo4j_client import Neo4jClient

SCHEMA_STATEMENTS = [
    # Unique constraints
    "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT class_id_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT func_id_unique IF NOT EXISTS FOR (fn:Function) REQUIRE fn.id IS UNIQUE",
    # Fast lookup indexes
    "CREATE INDEX func_name_idx IF NOT EXISTS FOR (fn:Function) ON (fn.name)",
    "CREATE INDEX class_name_idx IF NOT EXISTS FOR (c:Class) ON (c.name)",
    "CREATE INDEX file_path_idx IF NOT EXISTS FOR (f:File) ON (f.path)",
    # Vector index for 384-dimensional cosine embeddings
    """
    CREATE VECTOR INDEX function_embedding_idx IF NOT EXISTS
    FOR (fn:Function) ON (fn.embedding)
    OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
    """,
]


def init_schema(client: Neo4jClient) -> None:
    """Executes DDL statements to set up constraints and indexes in Neo4j."""
    for stmt in SCHEMA_STATEMENTS:
        client.execute_write(stmt)
