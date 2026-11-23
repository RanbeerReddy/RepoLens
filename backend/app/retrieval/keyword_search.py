"""Keyword and exact symbol search engine."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel

from app.graph.neo4j_client import Neo4jClient

KEYWORD_SEARCH_QUERY = """
MATCH (fn:Function)
WHERE ($repo_id IS NULL OR fn.repo_id = $repo_id)
  AND (
    fn.name = $term
    OR toLower(fn.name) = toLower($term)
    OR fn.qualified_name CONTAINS $term
  )
RETURN fn.id AS id,
       fn.name AS name,
       fn.qualified_name AS qualified_name,
       fn.file_path AS file_path,
       fn.start_line AS start_line,
       fn.end_line AS end_line,
       fn.signature AS signature,
       fn.docstring AS docstring,
       fn.source AS source
LIMIT $limit
"""


class KeywordResult(BaseModel):
    """Keyword search result with match score."""

    id: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    source: str
    score: float


class KeywordSearchEngine:
    """Finds code entities via exact identifier and substring matching."""

    def __init__(self, client: Optional[Neo4jClient] = None) -> None:
        self.client = client

    def search(
        self,
        query: str,
        limit: int = 10,
        repo_id: Optional[str] = None,
    ) -> list[KeywordResult]:
        """Searches Neo4j for functions matching identifiers extracted from the query."""
        terms = self._extract_identifiers(query)
        if not terms or not self.client:
            return []

        results_map: dict[str, KeywordResult] = {}
        for term in terms:
            records = self.client.execute_read(
                KEYWORD_SEARCH_QUERY,
                {"term": term, "limit": limit, "repo_id": repo_id},
            )
            for r in records:
                score = self._compute_score(term, r["name"], r["qualified_name"])
                if r["id"] not in results_map or score > results_map[r["id"]].score:
                    results_map[r["id"]] = KeywordResult(
                        id=r["id"],
                        name=r["name"],
                        qualified_name=r["qualified_name"],
                        file_path=r["file_path"],
                        start_line=r["start_line"],
                        end_line=r["end_line"],
                        signature=r["signature"],
                        docstring=r.get("docstring"),
                        source=r["source"],
                        score=score,
                    )

        sorted_results = sorted(results_map.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:limit]

    @staticmethod
    def search_in_memory(
        query: str,
        candidates: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[KeywordResult]:
        """In-memory keyword search over candidates for testing and offline fallback."""
        terms = KeywordSearchEngine._extract_identifiers(query)
        if not terms or not candidates:
            return []

        results: list[KeywordResult] = []
        for cand in candidates:
            best_score = 0.0
            for term in terms:
                score = KeywordSearchEngine._compute_score(
                    term, cand["name"], cand.get("qualified_name", "")
                )
                if score > best_score:
                    best_score = score

            if best_score > 0.0:
                results.append(
                    KeywordResult(
                        id=cand["id"],
                        name=cand["name"],
                        qualified_name=cand.get("qualified_name", cand["name"]),
                        file_path=cand["file_path"],
                        start_line=cand["start_line"],
                        end_line=cand["end_line"],
                        signature=cand.get("signature", f"def {cand['name']}()"),
                        docstring=cand.get("docstring"),
                        source=cand.get("source", ""),
                        score=best_score,
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    @staticmethod
    def _extract_identifiers(query: str) -> list[str]:
        """Extracts valid Python identifiers and keywords from query string."""
        raw_tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", query)
        stopwords = {
            "where",
            "is",
            "the",
            "in",
            "how",
            "what",
            "does",
            "do",
            "to",
            "and",
            "or",
            "of",
            "a",
            "an",
        }
        return [t for t in raw_tokens if t.lower() not in stopwords]

    @staticmethod
    def _compute_score(term: str, name: str, qualified_name: str) -> float:
        """Assigns normalized score based on match precision."""
        if term == name:
            return 1.0
        if term.lower() == name.lower():
            return 0.9
        if term in qualified_name.split("."):
            return 0.8
        if term.lower() in name.lower():
            return 0.6
        if term.lower() in qualified_name.lower():
            return 0.4
        return 0.0
