"""Impact-analysis service – traverse dependents and assess change impact."""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.core.errors import RetrievalError

if TYPE_CHECKING:
    from app.graph.operations import GraphOperations
    from app.llm.client import LLMClient

logger = logging.getLogger(__name__)


class ImpactReport(BaseModel):
    """Results of an impact analysis."""

    target_entity: dict = Field(default_factory=dict)
    direct_dependents: list[dict] = Field(default_factory=list)
    indirect_dependents: list[dict] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    dependency_paths: list[list[str]] = Field(default_factory=list)
    total_impact_count: int = 0
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)


class ImpactService:
    """Analyse the downstream impact of modifying a code entity."""

    def __init__(
        self,
        graph_ops: GraphOperations,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.graph_ops = graph_ops
        self.llm_client = llm_client

    async def analyze_impact(
        self,
        repo_id: str,
        entity_id_or_name: str,
        depth: int = 3,
    ) -> ImpactReport:
        """Find everything affected if *entity_id_or_name* were changed.

        Parameters
        ----------
        repo_id:
            Repository scope.
        entity_id_or_name:
            Either a full entity ID or a short name to look up.
        depth:
            Maximum traversal depth for indirect dependents.

        Returns
        -------
        ImpactReport
        """
        # --- Resolve entity ---------------------------------------------------
        entity = await self._resolve_entity(repo_id, entity_id_or_name)
        if entity is None:
            raise RetrievalError(
                message=f"Entity not found: {entity_id_or_name}",
                details={"repo_id": repo_id, "query": entity_id_or_name},
            )

        entity_id: str = entity["entity_id"]
        entity_name: str = entity.get("name", entity_id_or_name)

        # --- Direct dependents (depth=1) --------------------------------------
        direct_raw = await self._get_callers(entity_id, depth=1)
        direct_dependents = [
            self._node_to_dict(n) for n in direct_raw if n.get("entity_id") != entity_id
        ]

        # --- Indirect dependents (BFS up to *depth*) --------------------------
        indirect_dependents: list[dict] = []
        seen_ids: set[str] = {entity_id}
        seen_ids.update(d["entity_id"] for d in direct_dependents)
        dependency_paths: list[list[str]] = []

        queue: deque[tuple[str, list[str]]] = deque()
        for dep in direct_dependents:
            path = [entity_name, dep.get("name", dep["entity_id"])]
            queue.append((dep["entity_id"], path))

        current_depth = 1
        while queue and current_depth < depth:
            next_level: deque[tuple[str, list[str]]] = deque()
            while queue:
                dep_id, path_so_far = queue.popleft()
                callers = await self._get_callers(dep_id, depth=1)
                for caller in callers:
                    cid = caller.get("entity_id", "")
                    if cid in seen_ids or cid == entity_id:
                        continue
                    seen_ids.add(cid)
                    caller_dict = self._node_to_dict(caller)
                    indirect_dependents.append(caller_dict)
                    new_path = path_so_far + [caller_dict.get("name", cid)]
                    dependency_paths.append(new_path)
                    next_level.append((cid, new_path))
            queue = next_level
            current_depth += 1

        # Also record paths for direct dependents
        for dep in direct_dependents:
            dependency_paths.insert(0, [entity_name, dep.get("name", dep["entity_id"])])

        # --- Affected files ---------------------------------------------------
        affected_files_set: set[str] = set()
        for dep in direct_dependents + indirect_dependents:
            fp = dep.get("file_path", "")
            if fp:
                affected_files_set.add(fp)
        affected_files = sorted(affected_files_set)

        # --- Build report -----------------------------------------------------
        total_impact = len(direct_dependents) + len(indirect_dependents)

        limitations: list[str] = []
        if total_impact == 0:
            limitations.append("No dependents found – the entity may be unused or the graph incomplete.")
        limitations.append(f"Analysis limited to depth {depth}; deeper transitive effects may exist.")
        limitations.append("Dynamic calls (eval, getattr) are not captured by static analysis.")

        report = ImpactReport(
            target_entity=entity,
            direct_dependents=direct_dependents,
            indirect_dependents=indirect_dependents,
            affected_files=affected_files,
            dependency_paths=dependency_paths[:50],  # cap for readability
            total_impact_count=total_impact,
            summary="",
            limitations=limitations,
        )

        # --- Optional LLM summary --------------------------------------------
        if self.llm_client is not None:
            report.summary = await self._generate_summary(entity_name, report)

        if not report.summary:
            report.summary = (
                f"Modifying '{entity_name}' directly affects {len(direct_dependents)} "
                f"dependent(s) and indirectly affects {len(indirect_dependents)} more "
                f"across {len(affected_files)} file(s)."
            )

        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _resolve_entity(
        self, repo_id: str, entity_id_or_name: str
    ) -> dict | None:
        """Try to resolve by ID first, then by name search."""
        # Try as ID
        try:
            entity = await self.graph_ops.get_entity(entity_id_or_name)
            if entity:
                return entity
        except Exception:
            pass

        # Fallback: search by name
        try:
            results = await self.graph_ops.search_by_name(
                repo_id=repo_id, name_query=entity_id_or_name, limit=1
            )
            if results:
                return results[0]
        except Exception:
            logger.warning("Could not resolve entity: %s", entity_id_or_name)

        return None

    async def _get_callers(self, entity_id: str, depth: int = 1) -> list[dict]:
        """Return incoming dependents (callers) of *entity_id*."""
        try:
            return await self.graph_ops.get_neighbors(
                entity_id=entity_id,
                direction="incoming",
                depth=depth,
            )
        except Exception:
            logger.warning("Failed to get callers for %s", entity_id)
            return []

    async def _generate_summary(
        self, entity_name: str, report: ImpactReport
    ) -> str:
        """Use the LLM to produce a human-readable impact summary."""
        if self.llm_client is None:
            return ""

        from app.llm.prompts import build_impact_summary_prompt

        impact_data = report.model_dump(
            include={
                "direct_dependents",
                "indirect_dependents",
                "affected_files",
                "dependency_paths",
                "total_impact_count",
            }
        )
        messages = build_impact_summary_prompt(entity_name, impact_data)

        try:
            result = await self.llm_client.generate(messages, stream=False)
            if isinstance(result, str):
                return result
            return "".join([chunk async for chunk in result])
        except Exception as exc:
            logger.warning("LLM summary generation failed: %s", exc)
            return ""

    @staticmethod
    def _node_to_dict(node: dict) -> dict:
        """Normalise a raw graph record to a consistent dict."""
        return {
            "entity_id": node.get("entity_id", ""),
            "entity_type": node.get("entity_type", ""),
            "name": node.get("name", ""),
            "qualified_name": node.get("qualified_name", ""),
            "file_path": node.get("file_path", ""),
            "line_start": node.get("line_start"),
            "line_end": node.get("line_end"),
        }
