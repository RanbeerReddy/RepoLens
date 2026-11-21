"""Graph-based (keyword + neighbour expansion) retriever."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.retrieval.models import RetrievalResult

if TYPE_CHECKING:
    from app.graph.operations import GraphOperations

logger = logging.getLogger(__name__)


class GraphRetriever:
    """Retrieve entities via keyword matching and graph-neighbour expansion."""

    def __init__(self, graph_ops: GraphOperations) -> None:
        self.graph_ops = graph_ops

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        repo_id: str,
        query: str,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        """Keyword-search the graph and expand with neighbours.

        Parameters
        ----------
        repo_id:
            Repository to search within.
        query:
            Search string (matched against entity names).
        limit:
            Maximum number of results to return.

        Returns
        -------
        list[RetrievalResult]
        """
        try:
            raw_results = await self.graph_ops.search_by_name(
                repo_id=repo_id,
                name_query=query,
                limit=limit,
            )
        except Exception:
            logger.exception("Graph keyword search failed for repo %s", repo_id)
            return []

        results: list[RetrievalResult] = []
        seen_ids: set[str] = set()

        for record in raw_results:
            entity_id = record.get("entity_id", "")
            if entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)
            results.append(self._record_to_result(record, query))

        # Expand with neighbours for top results (at most half the limit)
        expansion_budget = max(1, limit // 2)
        for result in list(results[:expansion_budget]):
            neighbours = await self._get_neighbours(result.entity_id, depth=1)
            for neighbour in neighbours:
                if neighbour.entity_id not in seen_ids and len(results) < limit:
                    seen_ids.add(neighbour.entity_id)
                    neighbour.graph_context = f"Neighbour of {result.name}"
                    results.append(neighbour)

        return results[:limit]

    async def get_dependencies(
        self,
        entity_id: str,
        direction: str = "both",
        depth: int = 2,
    ) -> list[RetrievalResult]:
        """Traverse callers/callees of *entity_id*.

        Parameters
        ----------
        entity_id:
            The starting entity.
        direction:
            ``"incoming"`` (callers), ``"outgoing"`` (callees), or ``"both"``.
        depth:
            How many hops to traverse.

        Returns
        -------
        list[RetrievalResult]
        """
        try:
            raw = await self.graph_ops.get_neighbors(
                entity_id=entity_id,
                direction=direction,
                depth=depth,
            )
        except Exception:
            logger.exception("get_dependencies failed for %s", entity_id)
            return []

        seen: set[str] = set()
        results: list[RetrievalResult] = []
        for record in raw:
            eid = record.get("entity_id", "")
            if eid in seen or eid == entity_id:
                continue
            seen.add(eid)
            results.append(
                RetrievalResult(
                    entity_id=eid,
                    entity_type=record.get("entity_type", ""),
                    name=record.get("name", ""),
                    qualified_name=record.get("qualified_name", ""),
                    file_path=record.get("file_path", ""),
                    line_start=record.get("line_start"),
                    line_end=record.get("line_end"),
                    source=record.get("source", ""),
                    score=None,
                    retrieval_method="graph",
                    graph_context=f"Dependency of {entity_id} ({direction}, depth={depth})",
                    reason=f"Dependency traversal from {entity_id}",
                )
            )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_neighbours(
        self, entity_id: str, depth: int = 1
    ) -> list[RetrievalResult]:
        """Return immediate neighbours of *entity_id*."""
        try:
            raw = await self.graph_ops.get_neighbors(
                entity_id=entity_id,
                direction="both",
                depth=depth,
            )
        except Exception:
            logger.warning("Neighbour expansion failed for %s", entity_id)
            return []

        return [
            RetrievalResult(
                entity_id=r.get("entity_id", ""),
                entity_type=r.get("entity_type", ""),
                name=r.get("name", ""),
                qualified_name=r.get("qualified_name", ""),
                file_path=r.get("file_path", ""),
                line_start=r.get("line_start"),
                line_end=r.get("line_end"),
                source=r.get("source", ""),
                score=None,
                retrieval_method="graph",
                graph_context=None,
                reason="Neighbour expansion",
            )
            for r in raw
        ]

    @staticmethod
    def _record_to_result(record: dict, query: str) -> RetrievalResult:
        name = record.get("name", "")
        # Simple relevance heuristic: exact match → 1.0, substring → 0.7
        lower_name = name.lower()
        lower_query = query.lower()
        if lower_name == lower_query:
            score = 1.0
        elif lower_query in lower_name or lower_name in lower_query:
            score = 0.7
        else:
            score = 0.5

        return RetrievalResult(
            entity_id=record.get("entity_id", ""),
            entity_type=record.get("entity_type", ""),
            name=name,
            qualified_name=record.get("qualified_name", ""),
            file_path=record.get("file_path", ""),
            line_start=record.get("line_start"),
            line_end=record.get("line_end"),
            source=record.get("source", ""),
            score=score,
            retrieval_method="graph",
            graph_context=None,
            reason=f"Name match for '{query}'",
        )
