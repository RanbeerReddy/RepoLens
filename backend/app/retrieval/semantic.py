"""Semantic (vector-similarity) retriever."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.retrieval.models import RetrievalResult

if TYPE_CHECKING:
    from app.embeddings.generator import EmbeddingGenerator
    from app.graph.operations import GraphOperations

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """Retrieve entities by embedding-based vector similarity."""

    def __init__(
        self,
        graph_ops: GraphOperations,
        embedding_generator: EmbeddingGenerator,
    ) -> None:
        self.graph_ops = graph_ops
        self.embedding_generator = embedding_generator

    async def search(
        self,
        repo_id: str,
        query: str,
        limit: int = 10,
        entity_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Embed *query* and perform a vector search in the graph database.

        Parameters
        ----------
        repo_id:
            Repository to search within.
        query:
            Natural-language search query.
        limit:
            Maximum number of results to return.
        entity_type:
            Optional filter – e.g. ``"function"`` or ``"class"``.

        Returns
        -------
        list[RetrievalResult]
            Ranked results sorted by descending similarity score.
        """
        try:
            query_embedding = await self.embedding_generator.generate(query)
        except Exception:
            logger.exception("Failed to generate embedding for query: %s", query)
            return []

        try:
            raw_results = await self.graph_ops.vector_search(
                repo_id=repo_id,
                embedding=query_embedding,
                limit=limit,
                entity_type=entity_type,
            )
        except Exception:
            logger.exception("Vector search failed for repo %s", repo_id)
            return []

        results: list[RetrievalResult] = []
        for record in raw_results:
            results.append(
                RetrievalResult(
                    entity_id=record.get("entity_id", ""),
                    entity_type=record.get("entity_type", ""),
                    name=record.get("name", ""),
                    qualified_name=record.get("qualified_name", ""),
                    file_path=record.get("file_path", ""),
                    line_start=record.get("line_start"),
                    line_end=record.get("line_end"),
                    source=record.get("source", ""),
                    score=record.get("score"),
                    retrieval_method="semantic",
                    graph_context=None,
                    reason=f"Semantic similarity to query '{query}'",
                )
            )

        return results
