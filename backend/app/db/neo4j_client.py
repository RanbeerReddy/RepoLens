"""Async Neo4j driver wrapper."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.core.errors import GraphError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_client_instance: Optional["Neo4jClient"] = None


class Neo4jClient:
    """Thin async wrapper around the Neo4j Python driver."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver: Optional[AsyncDriver] = None

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Create the async driver and verify connectivity."""
        try:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
            )
            await self.verify_connectivity()
            logger.info("Connected to Neo4j at %s (db=%s)", self._uri, self._database)
        except (ServiceUnavailable, AuthError, OSError) as exc:
            logger.error("Failed to connect to Neo4j: %s", exc)
            raise GraphError(
                "Cannot connect to Neo4j",
                details={"uri": self._uri, "error": str(exc)},
            ) from exc

    async def close(self) -> None:
        """Close the driver, releasing all resources."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    async def verify_connectivity(self) -> None:
        """Ping the server to confirm the connection is alive."""
        if self._driver is None:
            raise GraphError("Driver not initialised; call connect() first")
        try:
            await self._driver.verify_connectivity()
        except Exception as exc:
            raise GraphError(
                "Neo4j connectivity check failed", details={"error": str(exc)}
            ) from exc

    # -- query helpers -------------------------------------------------------

    def _ensure_driver(self) -> AsyncDriver:
        if self._driver is None:
            raise GraphError("Driver not initialised; call connect() first")
        return self._driver

    async def execute_read(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run a read transaction and return a list of record dicts."""
        driver = self._ensure_driver()

        async def _work(tx: AsyncSession) -> List[Dict[str, Any]]:
            result = await tx.run(query, parameters=params or {})
            return [record.data() async for record in result]

        try:
            async with driver.session(database=self._database) as session:
                return await session.execute_read(lambda tx: _work(tx))
        except Exception as exc:
            logger.error("Read query failed: %s", exc)
            raise GraphError(
                "Read query failed",
                details={"query": query, "error": str(exc)},
            ) from exc

    async def execute_write(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run a write transaction and return a list of record dicts."""
        driver = self._ensure_driver()

        async def _work(tx: AsyncSession) -> List[Dict[str, Any]]:
            result = await tx.run(query, parameters=params or {})
            return [record.data() async for record in result]

        try:
            async with driver.session(database=self._database) as session:
                return await session.execute_write(lambda tx: _work(tx))
        except Exception as exc:
            logger.error("Write query failed: %s", exc)
            raise GraphError(
                "Write query failed",
                details={"query": query, "error": str(exc)},
            ) from exc


def get_neo4j_client() -> Neo4jClient:
    """Return the module-level :class:`Neo4jClient` singleton.

    The client is instantiated lazily from the current settings on first call.
    """
    global _client_instance  # noqa: PLW0603
    if _client_instance is None:
        from app.core.config import get_settings

        settings = get_settings()
        _client_instance = Neo4jClient(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
            database=settings.NEO4J_DATABASE,
        )
    return _client_instance
