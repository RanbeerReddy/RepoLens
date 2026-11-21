"""FastAPI dependency-injection helpers."""

from __future__ import annotations

from app.core.config import Settings
from app.core.config import get_settings as _get_settings
from app.db.neo4j_client import Neo4jClient
from app.db.neo4j_client import get_neo4j_client as _get_neo4j_client


def get_db() -> Neo4jClient:
    """Return the :class:`Neo4jClient` singleton for use as a FastAPI dependency."""
    return _get_neo4j_client()


def get_settings() -> Settings:
    """Return the cached :class:`Settings` for use as a FastAPI dependency."""
    return _get_settings()
