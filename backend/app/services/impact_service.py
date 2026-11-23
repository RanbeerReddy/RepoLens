"""Change Impact Analysis Service.

Computes the blast radius of modifying a Python function by traversing caller
graphs, isolating affected modules, identifying relevant test files, and
generating an evidence-based risk assessment.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.graph.neo4j_client import Neo4jClient
from app.llm.vllm_client import LLMError, VLLMClient


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DependentEntity(BaseModel):
    """Represents a calling function or callee dependency."""

    id: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    depth: int = 1
    is_method: bool = False


class ImpactReport(BaseModel):
    """Complete change impact assessment report."""

    target_function: str
    target_qualified_name: str
    target_file_path: str
    impact_level: ImpactLevel
    heuristic_rationale: str
    direct_callers: list[DependentEntity] = Field(default_factory=list)
    indirect_callers: list[DependentEntity] = Field(default_factory=list)
    callees: list[DependentEntity] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    relevant_tests: list[str] = Field(default_factory=list)
    dependency_paths: list[str] = Field(default_factory=list)
    analysis_summary: str
    llm_used: bool = True
    disclaimer: str = (
        "Impact is based on statically detected AST dependencies. "
        "Dynamic calls (e.g. getattr, runtime dispatch, decorators) may not be detected."
    )


REVERSE_CALLERS_QUERY = """
MATCH path = (caller:Function)-[:CALLS*1..3]->(target:Function)
WHERE (target.id = $func_identifier OR target.name = $func_identifier)
  AND ($repo_id IS NULL OR target.repo_id = $repo_id)
RETURN [n IN nodes(path) | {
    id: n.id,
    name: n.name,
    qualified_name: n.qualified_name,
    file_path: n.file_path,
    start_line: n.start_line,
    end_line: n.end_line,
    is_method: n.is_method
}] AS path_nodes,
length(path) AS depth
ORDER BY depth ASC
"""

CALLEES_QUERY = """
MATCH (target:Function)-[:CALLS]->(callee:Function)
WHERE (target.id = $func_identifier OR target.name = $func_identifier)
  AND ($repo_id IS NULL OR target.repo_id = $repo_id)
RETURN DISTINCT callee.id AS id,
       callee.name AS name,
       callee.qualified_name AS qualified_name,
       callee.file_path AS file_path,
       callee.start_line AS start_line,
       callee.end_line AS end_line,
       callee.is_method AS is_method
ORDER BY callee.file_path, callee.start_line
"""

TARGET_DETAILS_QUERY = """
MATCH (target:Function)
WHERE (target.id = $func_identifier OR target.name = $func_identifier)
  AND ($repo_id IS NULL OR target.repo_id = $repo_id)
RETURN target.id AS id,
       target.name AS name,
       target.qualified_name AS qualified_name,
       target.file_path AS file_path
LIMIT 1
"""


class ImpactService:
    """Computes blast-radius impact reports for codebase changes."""

    def __init__(
        self,
        neo4j_client: Optional[Neo4jClient] = None,
        llm_client: Optional[VLLMClient] = None,
    ) -> None:
        self.client = neo4j_client
        self.llm_client = llm_client or VLLMClient()

    def analyze_impact(
        self,
        function_identifier: str,
        repo_id: Optional[str] = None,
    ) -> ImpactReport:
        """
        Executes reverse call graph traversal and returns structured impact report.
        """
        target_info = self._get_target_info(function_identifier, repo_id)
        target_name = target_info.get("name", function_identifier)
        target_qual = target_info.get("qualified_name", target_name)
        target_file = target_info.get("file_path", "unknown")

        direct_callers: list[DependentEntity] = []
        indirect_callers: list[DependentEntity] = []
        dependency_paths: list[str] = []
        seen_caller_ids: set[str] = set()

        if self.client:
            records = self.client.execute_read(
                REVERSE_CALLERS_QUERY,
                {"func_identifier": function_identifier, "repo_id": repo_id},
            )
            for r in records:
                nodes = r["path_nodes"]
                depth = r["depth"]
                caller_node = nodes[0]  # Originating caller

                # Build readable path string: foo() -> bar() -> target()
                chain = " -> ".join(f"{n['name']}()" for n in nodes)
                if chain not in dependency_paths:
                    dependency_paths.append(chain)

                if caller_node["id"] not in seen_caller_ids and caller_node[
                    "id"
                ] != target_info.get("id"):
                    seen_caller_ids.add(caller_node["id"])
                    dep = DependentEntity(
                        id=caller_node["id"],
                        name=caller_node["name"],
                        qualified_name=caller_node["qualified_name"],
                        file_path=caller_node["file_path"],
                        start_line=caller_node["start_line"],
                        end_line=caller_node["end_line"],
                        depth=depth,
                        is_method=caller_node.get("is_method", False),
                    )
                    if depth == 1:
                        direct_callers.append(dep)
                    else:
                        indirect_callers.append(dep)

        # Callee lookup
        callees: list[DependentEntity] = []
        if self.client:
            callee_records = self.client.execute_read(
                CALLEES_QUERY,
                {"func_identifier": function_identifier, "repo_id": repo_id},
            )
            for cr in callee_records:
                callees.append(
                    DependentEntity(
                        id=cr["id"],
                        name=cr["name"],
                        qualified_name=cr["qualified_name"],
                        file_path=cr["file_path"],
                        start_line=cr["start_line"],
                        end_line=cr["end_line"],
                        depth=1,
                        is_method=cr.get("is_method", False),
                    )
                )

        # Compute affected files and tests
        all_callers = direct_callers + indirect_callers
        affected_files = sorted({c.file_path for c in all_callers if c.file_path})
        if target_file != "unknown" and target_file not in affected_files:
            affected_files.insert(0, target_file)

        relevant_tests = [
            f for f in affected_files if "test" in f.lower() or f.startswith("tests/")
        ]

        # Heuristic impact classification
        impact_level, rationale = self._classify_impact(
            direct_count=len(direct_callers),
            indirect_count=len(indirect_callers),
            module_count=len(affected_files),
        )

        # LLM Summary Generation
        summary, llm_used = self._generate_summary(
            target_name=target_name,
            target_file=target_file,
            impact_level=impact_level,
            direct_callers=direct_callers,
            indirect_callers=indirect_callers,
            affected_files=affected_files,
            rationale=rationale,
        )

        return ImpactReport(
            target_function=target_name,
            target_qualified_name=target_qual,
            target_file_path=target_file,
            impact_level=impact_level,
            heuristic_rationale=rationale,
            direct_callers=direct_callers,
            indirect_callers=indirect_callers,
            callees=callees,
            affected_files=affected_files,
            relevant_tests=relevant_tests,
            dependency_paths=dependency_paths,
            analysis_summary=summary,
            llm_used=llm_used,
        )

    def _get_target_info(self, identifier: str, repo_id: Optional[str]) -> dict[str, Any]:
        """Resolves target function metadata."""
        if not self.client:
            return {"name": identifier, "qualified_name": identifier, "file_path": "unknown"}
        records = self.client.execute_read(
            TARGET_DETAILS_QUERY,
            {"func_identifier": identifier, "repo_id": repo_id},
        )
        return (
            records[0]
            if records
            else {"name": identifier, "qualified_name": identifier, "file_path": "unknown"}
        )

    @staticmethod
    def _classify_impact(
        direct_count: int,
        indirect_count: int,
        module_count: int,
    ) -> tuple[ImpactLevel, str]:
        """
        Deterministic, transparent heuristic impact tiering:
        - LOW: <=2 direct callers, <=2 indirect callers, <=2 files affected.
        - HIGH: >5 direct callers OR >3 files affected.
        - MEDIUM: all intermediate blast radiuses.
        """
        if direct_count == 0 and indirect_count == 0:
            return (
                ImpactLevel.LOW,
                "Leaf or entrypoint function with zero detected upstream callers.",
            )

        if direct_count <= 2 and indirect_count <= 2 and module_count <= 2:
            return (
                ImpactLevel.LOW,
                f"Isolated scope: affects {direct_count} caller(s) across {module_count} file(s).",
            )

        if direct_count > 5 or module_count > 3:
            return (
                ImpactLevel.HIGH,
                f"Wide blast radius: {direct_count} callers across {module_count} files.",
            )

        return (
            ImpactLevel.MEDIUM,
            f"Moderate scope: {direct_count} direct and {indirect_count} indirect caller(s).",
        )

    def _generate_summary(
        self,
        target_name: str,
        target_file: str,
        impact_level: ImpactLevel,
        direct_callers: list[DependentEntity],
        indirect_callers: list[DependentEntity],
        affected_files: list[str],
        rationale: str,
    ) -> tuple[str, bool]:
        """Generates concise risk explanation with vLLM or deterministic template fallback."""
        direct_str = ", ".join(f"{c.name}()" for c in direct_callers) or "None"
        files_str = ", ".join(affected_files)

        prompt = (
            f"Target Function: {target_name}() in {target_file}\n"
            f"Heuristic Impact Level: {impact_level.value}\n"
            f"Direct Callers: {direct_str}\n"
            f"Affected Files: {files_str}\n"
            f"Heuristic Rationale: {rationale}\n\n"
            "Summarize the potential change impact in 2-3 concise sentences. "
            "Highlight what components could break if the function interface changes."
        )

        try:
            summary = self.llm_client.generate(prompt)
            return summary, True
        except LLMError:
            # Deterministic fallback when LLM is offline
            fallback = (
                f"Modifying '{target_name}()' carries {impact_level.value.lower()} impact. "
                f"{rationale} "
                f"Direct dependents to review: {direct_str} in {files_str}."
            )
            return fallback, False
