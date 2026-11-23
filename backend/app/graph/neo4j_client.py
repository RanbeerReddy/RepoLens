"""Neo4j client connection and session management."""

from __future__ import annotations

from typing import Any, Optional

from neo4j import Driver, GraphDatabase

from app.core.config import settings


class Neo4jClient:
    """Manages connections, transactions, and sessions with Neo4j."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self.uri = uri or settings.neo4j_uri
        self.auth = (user or settings.neo4j_user, password or settings.neo4j_password)
        self.database = database or settings.neo4j_database
        self._driver: Optional[Driver] = None

    @property
    def driver(self) -> Driver:
        """Returns or lazily creates the Neo4j driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=self.auth,
                max_connection_lifetime=3600,
            )
        return self._driver

    def close(self) -> None:
        """Closes any active driver connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def execute_write(
        self, query: str, parameters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Executes a write transaction query with parameters."""
        with self.driver.session(database=self.database) as session:
            return session.execute_write(
                lambda tx: [record.data() for record in tx.run(query, parameters or {})]
            )

    def execute_read(
        self, query: str, parameters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Executes a read transaction query with parameters."""
        with self.driver.session(database=self.database) as session:
            return session.execute_read(
                lambda tx: [record.data() for record in tx.run(query, parameters or {})]
            )

    def ping(self) -> bool:
        """Returns True if Neo4j is reachable and responding."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False
