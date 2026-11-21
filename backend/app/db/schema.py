"""Neo4j schema initialisation — constraints, indexes, and vector indexes."""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


async def init_schema(client: Neo4jClient) -> None:
    """Create all required uniqueness constraints and indexes.

    Each statement is wrapped in its own ``try / except`` so that
    already-existing constraints or indexes do not abort the process.
    """

    # ── Uniqueness constraints ───────────────────────────────────────────
    unique_constraints: list[tuple[str, str, str]] = [
        ("repo_id_unique", "Repository", "id"),
        ("file_id_unique", "File", "id"),
        ("class_id_unique", "Class", "id"),
        ("function_id_unique", "Function", "id"),
        ("module_id_unique", "Module", "id"),
    ]

    for name, label, prop in unique_constraints:
        query = (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        try:
            await client.execute_write(query)
            logger.info("Constraint ensured: %s", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not create constraint %s: %s", name, exc)

    # ── Property indexes ─────────────────────────────────────────────────
    indexes: list[tuple[str, str, str]] = [
        ("file_path_idx", "File", "path"),
        ("function_qname_idx", "Function", "qualified_name"),
        ("class_qname_idx", "Class", "qualified_name"),
        ("function_name_idx", "Function", "name"),
        ("class_name_idx", "Class", "name"),
    ]

    for name, label, prop in indexes:
        query = (
            f"CREATE INDEX {name} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.{prop})"
        )
        try:
            await client.execute_write(query)
            logger.info("Index ensured: %s", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not create index %s: %s", name, exc)

    # ── Vector indexes (may not be supported on all Neo4j editions) ──────
    settings = get_settings()
    dimension = settings.EMBEDDING_DIMENSION

    vector_indexes: list[tuple[str, str]] = [
        ("function_embedding_vector", "Function"),
        ("class_embedding_vector", "Class"),
    ]

    for name, label in vector_indexes:
        query = (
            f"CREATE VECTOR INDEX {name} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.embedding) "
            f"OPTIONS {{indexConfig: {{"
            f"`vector.dimensions`: {dimension}, "
            f"`vector.similarity_function`: 'cosine'"
            f"}}}}"
        )
        try:
            await client.execute_write(query)
            logger.info("Vector index ensured: %s", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not create vector index %s (may be unsupported): %s",
                name,
                exc,
            )
