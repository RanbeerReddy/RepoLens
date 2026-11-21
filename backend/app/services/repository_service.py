"""Repository management service."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.core.errors import RepositoryNotFoundError, ValidationError
from app.core.security import validate_repo_path

if TYPE_CHECKING:
    from app.graph.operations import GraphOperations

logger = logging.getLogger(__name__)


class RepositoryService:
    """CRUD operations for repository entities in the graph database."""

    def __init__(self, graph_ops: GraphOperations) -> None:
        self.graph_ops = graph_ops

    async def create(
        self,
        path: str,
        name: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Register a new repository.

        Parameters
        ----------
        path:
            Absolute filesystem path to the repository root.
        name:
            Human-readable name (defaults to directory name).
        description:
            Optional description.

        Returns
        -------
        dict
            ``{"id", "name", "path", "description"}``
        """
        validated_path = validate_repo_path(path)

        repo_name = name or validated_path.name
        repo_id = str(uuid.uuid4())

        # Check for duplicate path
        existing = await self.list_all()
        for repo in existing:
            if repo.get("path") == str(validated_path):
                raise ValidationError(
                    message=f"Repository already registered at {validated_path}",
                    details={"existing_id": repo.get("id")},
                )

        repo_data = {
            "id": repo_id,
            "name": repo_name,
            "path": str(validated_path),
            "description": description or "",
        }

        await self.graph_ops.create_repository(repo_data)

        logger.info("Created repository '%s' (id=%s) at %s", repo_name, repo_id, validated_path)
        return repo_data

    async def get(self, repo_id: str) -> dict:
        """Fetch a repository by ID.

        Raises
        ------
        RepositoryNotFoundError
            If no repository with *repo_id* exists.
        """
        repo = await self.graph_ops.get_repository(repo_id)
        if repo is None:
            raise RepositoryNotFoundError(
                message=f"Repository not found: {repo_id}",
                details={"repo_id": repo_id},
            )
        return repo

    async def list_all(self) -> list[dict]:
        """Return all registered repositories."""
        try:
            return await self.graph_ops.list_repositories()
        except Exception:
            logger.exception("Failed to list repositories")
            return []

    async def delete(self, repo_id: str) -> None:
        """Delete a repository and all its entities.

        Raises
        ------
        RepositoryNotFoundError
            If no repository with *repo_id* exists.
        """
        # Verify existence first
        await self.get(repo_id)
        await self.graph_ops.delete_repository(repo_id)
        logger.info("Deleted repository %s", repo_id)

    async def get_stats(self, repo_id: str) -> dict:
        """Return aggregate statistics for a repository.

        Returns
        -------
        dict
            Keys: ``repo_id``, ``total_files``, ``total_functions``,
            ``total_classes``, ``total_modules``.
        """
        # Verify existence
        await self.get(repo_id)

        try:
            stats = await self.graph_ops.get_repository_stats(repo_id)
        except Exception:
            logger.exception("Failed to get stats for repo %s", repo_id)
            stats = {}

        return {
            "repo_id": repo_id,
            "total_files": stats.get("total_files", 0),
            "total_functions": stats.get("total_functions", 0),
            "total_classes": stats.get("total_classes", 0),
            "total_modules": stats.get("total_modules", 0),
        }
