"""High-performance batched graph ingester for Neo4j."""

from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.parser.models import ParsedRepository

# Batched Cypher Statements
MERGE_REPO = """
MERGE (r:Repository {id: $repo.id})
SET r.name = $repo.name,
    r.root_path = $repo.root_path,
    r.total_files = $repo.total_files,
    r.total_functions = $repo.total_functions,
    r.total_classes = $repo.total_classes,
    r.total_lines = $repo.total_lines
"""

UNWIND_FILES = """
UNWIND $batch AS row
MATCH (r:Repository {id: row.repo_id})
MERGE (f:File {id: row.id})
SET f.path = row.path,
    f.hash = row.hash,
    f.size_bytes = row.size_bytes,
    f.total_lines = row.total_lines,
    f.repo_id = row.repo_id
MERGE (r)-[:CONTAINS]->(f)
"""

UNWIND_CLASSES = """
UNWIND $batch AS row
MATCH (f:File {id: row.file_id})
MERGE (c:Class {id: row.id})
SET c.name = row.name,
    c.qualified_name = row.qualified_name,
    c.file_path = row.file_path,
    c.docstring = row.docstring,
    c.start_line = row.start_line,
    c.end_line = row.end_line,
    c.repo_id = row.repo_id
MERGE (f)-[:DEFINES]->(c)
"""

UNWIND_FUNCTIONS = """
UNWIND $batch AS row
MATCH (f:File {id: row.file_id})
MERGE (fn:Function {id: row.id})
SET fn.name = row.name,
    fn.qualified_name = row.qualified_name,
    fn.file_path = row.file_path,
    fn.signature = row.signature,
    fn.docstring = row.docstring,
    fn.source = row.source,
    fn.start_line = row.start_line,
    fn.end_line = row.end_line,
    fn.is_method = row.is_method,
    fn.is_async = row.is_async,
    fn.repo_id = row.repo_id
MERGE (f)-[:DEFINES]->(fn)
WITH row, fn
WHERE row.class_id IS NOT NULL
MATCH (c:Class {id: row.class_id})
MERGE (c)-[:HAS_METHOD]->(fn)
"""

UNWIND_INHERITANCE = """
UNWIND $batch AS row
MATCH (child:Class {id: row.class_id})
MATCH (parent:Class {name: row.base_name, repo_id: row.repo_id})
MERGE (child)-[:INHERITS]->(parent)
"""

UNWIND_CALLS = """
UNWIND $batch AS row
MATCH (caller:Function {id: row.caller_id})
MATCH (target:Function {name: row.callee_name, repo_id: row.repo_id})
MERGE (caller)-[:CALLS]->(target)
"""


class GraphIngester:
    """Transforms a ParsedRepository into batched Neo4j graph nodes and edges."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def ingest_repository(
        self, parsed_repo: ParsedRepository, repo_id: str | None = None
    ) -> dict[str, int]:
        """
        Ingests the parsed repository using batched transactions.

        Returns ingestion statistics.
        """
        r_id = repo_id or f"repo:{parsed_repo.repo_name}"

        # 1. Compile batches
        files_batch: list[dict[str, Any]] = []
        classes_batch: list[dict[str, Any]] = []
        functions_batch: list[dict[str, Any]] = []
        inherits_batch: list[dict[str, Any]] = []
        calls_batch: list[dict[str, Any]] = []

        for f in parsed_repo.files:
            file_node_id = f"file:{r_id}:{f.file_path}"
            files_batch.append(
                {
                    "id": file_node_id,
                    "path": f.file_path,
                    "hash": f.file_hash,
                    "size_bytes": f.size_bytes,
                    "total_lines": f.total_lines,
                    "repo_id": r_id,
                }
            )

            # Classes
            for c in f.classes:
                class_node_id = f"class:{r_id}:{f.file_path}:{c.name}"
                classes_batch.append(
                    {
                        "id": class_node_id,
                        "name": c.name,
                        "qualified_name": c.qualified_name,
                        "file_id": file_node_id,
                        "file_path": f.file_path,
                        "docstring": c.docstring,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "repo_id": r_id,
                    }
                )

                for base in c.bases:
                    inherits_batch.append(
                        {
                            "class_id": class_node_id,
                            "base_name": base.split(".")[-1],
                            "repo_id": r_id,
                        }
                    )

                # Methods
                for m in c.methods:
                    method_id = f"func:{r_id}:{f.file_path}:{c.name}:{m.name}"
                    functions_batch.append(
                        self._func_to_row(
                            m, method_id, file_node_id, f.file_path, r_id, class_node_id
                        )
                    )
                    for callee in m.calls:
                        calls_batch.append(
                            {"caller_id": method_id, "callee_name": callee, "repo_id": r_id}
                        )

            # Top-level Functions
            for fn in f.functions:
                fn_id = f"func:{r_id}:{f.file_path}:global:{fn.name}"
                functions_batch.append(
                    self._func_to_row(fn, fn_id, file_node_id, f.file_path, r_id, None)
                )
                for callee in fn.calls:
                    calls_batch.append({"caller_id": fn_id, "callee_name": callee, "repo_id": r_id})

        # 2. Execute batched transactions
        repo_data = {
            "id": r_id,
            "name": parsed_repo.repo_name,
            "root_path": parsed_repo.root_path,
            "total_files": parsed_repo.total_files,
            "total_functions": parsed_repo.total_functions,
            "total_classes": parsed_repo.total_classes,
            "total_lines": parsed_repo.total_lines,
        }

        self.client.execute_write(MERGE_REPO, {"repo": repo_data})
        if files_batch:
            self.client.execute_write(UNWIND_FILES, {"batch": files_batch})
        if classes_batch:
            self.client.execute_write(UNWIND_CLASSES, {"batch": classes_batch})
        if functions_batch:
            self.client.execute_write(UNWIND_FUNCTIONS, {"batch": functions_batch})
        if inherits_batch:
            self.client.execute_write(UNWIND_INHERITANCE, {"batch": inherits_batch})
        if calls_batch:
            self.client.execute_write(UNWIND_CALLS, {"batch": calls_batch})

        return {
            "files": len(files_batch),
            "classes": len(classes_batch),
            "functions": len(functions_batch),
            "calls": len(calls_batch),
            "inherits": len(inherits_batch),
        }

    @staticmethod
    def _func_to_row(
        fn: Any, fn_id: str, file_id: str, file_path: str, repo_id: str, class_id: str | None
    ) -> dict[str, Any]:
        return {
            "id": fn_id,
            "name": fn.name,
            "qualified_name": fn.qualified_name,
            "file_id": file_id,
            "file_path": file_path,
            "signature": fn.signature,
            "docstring": fn.docstring,
            "source": fn.source,
            "start_line": fn.start_line,
            "end_line": fn.end_line,
            "is_method": fn.is_method,
            "is_async": fn.is_async,
            "repo_id": repo_id,
            "class_id": class_id,
        }
