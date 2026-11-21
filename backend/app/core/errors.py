"""Custom exception hierarchy for RepoLens."""

from __future__ import annotations

from typing import Any, Dict, Optional


class RepoLensError(Exception):
    """Base exception for all RepoLens errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.message = message
        self.details: Dict[str, Any] = details or {}
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details!r})"


class RepositoryNotFoundError(RepoLensError):
    """Raised when a requested repository does not exist."""


class IngestionError(RepoLensError):
    """Raised when repository ingestion fails."""


class ParserError(RepoLensError):
    """Raised when source-code parsing fails."""


class GraphError(RepoLensError):
    """Raised when a graph database operation fails."""


class EmbeddingError(RepoLensError):
    """Raised when embedding generation fails."""


class RetrievalError(RepoLensError):
    """Raised when context retrieval fails."""


class LLMError(RepoLensError):
    """Raised when an LLM call fails."""


class ValidationError(RepoLensError):
    """Raised when input validation fails."""
