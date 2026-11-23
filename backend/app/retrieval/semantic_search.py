"""Semantic code search using Neo4j vector index with in-memory fallback."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field

from app.embeddings.embedder import CodeEmbedder
from app.graph.neo4j_client import Neo4jClient

UNWIND_STORE_EMBEDDINGS = """
UNWIND $batch AS row
MATCH (fn:Function {id: row.id})
SET fn.embedding = row.embedding
"""

VECTOR_SEARCH_QUERY = """
CALL db.index.vector.queryNodes('function_embedding_idx', $limit, $query_embedding)
YIELD node, score
WHERE ($repo_id IS NULL OR node.repo_id = $repo_id)
RETURN node.id AS id,
       node.name AS name,
       node.qualified_name AS qualified_name,
       node.file_path AS file_path,
       node.start_line AS start_line,
       node.end_line AS end_line,
       node.signature AS signature,
       node.docstring AS docstring,
       node.source AS source,
       score
ORDER BY score DESC
"""


class SearchResult(BaseModel):
    """Semantic search candidate entity with similarity score."""

    id: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    source: str
    score: float = Field(description="Cosine similarity score (0.0 to 1.0)")


class SemanticSearchEngine:
    """High-performance semantic code search engine."""

    def __init__(
        self,
        client: Optional[Neo4jClient] = None,
        embedder: Optional[CodeEmbedder] = None,
    ) -> None:
        self.client = client
        self.embedder = embedder or CodeEmbedder()

    def store_function_embeddings(self, functions_with_embeddings: list[dict[str, Any]]) -> int:
        """
        Stores precomputed embedding vectors on Function nodes in Neo4j.
        Input format: [{'id': func_id, 'embedding': [float, ...]}]
        """
        if not self.client or not functions_with_embeddings:
            return 0
        self.client.execute_write(
            UNWIND_STORE_EMBEDDINGS,
            {"batch": functions_with_embeddings},
        )
        return len(functions_with_embeddings)

    def search(
        self,
        query: str,
        limit: int = 10,
        repo_id: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Executes semantic search against Neo4j vector index.
        """
        query_vector = self.embedder.embed_query(query)
        if not self.client:
            return []

        records = self.client.execute_read(
            VECTOR_SEARCH_QUERY,
            {
                "limit": limit,
                "query_embedding": query_vector,
                "repo_id": repo_id,
            },
        )

        return [
            SearchResult(
                id=r["id"],
                name=r["name"],
                qualified_name=r["qualified_name"],
                file_path=r["file_path"],
                start_line=r["start_line"],
                end_line=r["end_line"],
                signature=r["signature"],
                docstring=r.get("docstring"),
                source=r["source"],
                score=float(r["score"]),
            )
            for r in records
        ]

    @staticmethod
    def search_in_memory(
        query_vector: list[float],
        candidates: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        In-memory cosine similarity search over local candidate embeddings.
        Used for unit tests, local evaluation, or fallback when Neo4j vector index is offline.
        """
        if not candidates:
            return []

        matrix = np.array([c["embedding"] for c in candidates], dtype=np.float32)
        q = np.array(query_vector, dtype=np.float32)

        # Dot product of normalized vectors equals cosine similarity
        norm_matrix = np.linalg.norm(matrix, axis=1, keepdims=True)
        norm_q = np.linalg.norm(q)
        if norm_q == 0:
            return []

        matrix_norm = matrix / np.maximum(norm_matrix, 1e-9)
        q_norm = q / norm_q
        scores = np.dot(matrix_norm, q_norm)

        top_indices = np.argsort(scores)[::-1][:limit]

        results: list[SearchResult] = []
        for idx in top_indices:
            cand = candidates[idx]
            results.append(
                SearchResult(
                    id=cand["id"],
                    name=cand["name"],
                    qualified_name=cand["qualified_name"],
                    file_path=cand["file_path"],
                    start_line=cand["start_line"],
                    end_line=cand["end_line"],
                    signature=cand["signature"],
                    docstring=cand.get("docstring"),
                    source=cand["source"],
                    score=float(scores[idx]),
                )
            )
        return results
