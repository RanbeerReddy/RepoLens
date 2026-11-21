"""Hybrid retriever – combines semantic and graph retrieval."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.retrieval.models import RetrievalResult

if TYPE_CHECKING:
    from app.retrieval.graph_retriever import GraphRetriever
    from app.retrieval.semantic import SemanticRetriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Merge semantic and graph retrieval results with configurable weights."""

    def __init__(
        self,
        semantic_retriever: SemanticRetriever,
        graph_retriever: GraphRetriever,
    ) -> None:
        self.semantic_retriever = semantic_retriever
        self.graph_retriever = graph_retriever

    async def search(
        self,
        repo_id: str,
        query: str,
        limit: int = 10,
        semantic_weight: float = 0.6,
        graph_weight: float = 0.4,
    ) -> list[RetrievalResult]:
        """Run both retrievers, deduplicate, merge scores, and rank.

        Parameters
        ----------
        repo_id:
            Repository to search.
        query:
            Natural-language query.
        limit:
            Max results to return.
        semantic_weight:
            Weight applied to semantic scores (0-1).
        graph_weight:
            Weight applied to graph scores (0-1).

        Returns
        -------
        list[RetrievalResult]
            Top *limit* results sorted by combined score descending.
        """
        # Run both retrievers concurrently
        import asyncio

        semantic_task = asyncio.create_task(
            self.semantic_retriever.search(repo_id, query, limit=limit)
        )
        graph_task = asyncio.create_task(
            self.graph_retriever.search(repo_id, query, limit=limit)
        )

        semantic_results, graph_results = await asyncio.gather(
            semantic_task, graph_task, return_exceptions=True
        )

        if isinstance(semantic_results, BaseException):
            logger.warning("Semantic retriever failed: %s", semantic_results)
            semantic_results = []
        if isinstance(graph_results, BaseException):
            logger.warning("Graph retriever failed: %s", graph_results)
            graph_results = []

        # Merge into a dict keyed by entity_id
        merged: dict[str, _MergedEntry] = {}

        for result in semantic_results:
            merged[result.entity_id] = _MergedEntry(
                result=result,
                semantic_score=result.score or 0.0,
                graph_score=0.0,
            )

        for result in graph_results:
            if result.entity_id in merged:
                entry = merged[result.entity_id]
                entry.graph_score = result.score or 0.0
                # Keep richer graph context if available
                if result.graph_context:
                    entry.result.graph_context = result.graph_context
            else:
                merged[result.entity_id] = _MergedEntry(
                    result=result,
                    semantic_score=0.0,
                    graph_score=result.score or 0.0,
                )

        # Compute combined scores and build final list
        ranked: list[RetrievalResult] = []
        for entry in merged.values():
            combined = (
                entry.semantic_score * semantic_weight
                + entry.graph_score * graph_weight
            )
            result = entry.result.model_copy()
            result.score = round(combined, 4)
            result.retrieval_method = "hybrid"
            if entry.semantic_score > 0 and entry.graph_score > 0:
                result.reason = "Matched by both semantic similarity and graph keyword search"
            elif entry.semantic_score > 0:
                result.reason = "Matched by semantic similarity"
            else:
                result.reason = "Matched by graph keyword search"
            ranked.append(result)

        ranked.sort(key=lambda r: r.score or 0.0, reverse=True)
        return ranked[:limit]


class _MergedEntry:
    """Temporary container used while merging scores."""

    __slots__ = ("result", "semantic_score", "graph_score")

    def __init__(
        self,
        result: RetrievalResult,
        semantic_score: float,
        graph_score: float,
    ) -> None:
        self.result = result
        self.semantic_score = semantic_score
        self.graph_score = graph_score
