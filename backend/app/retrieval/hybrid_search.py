"""Hybrid Retrieval Engine combining Semantic, Keyword, and Graph Channels."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.embeddings.embedder import CodeEmbedder
from app.graph.neo4j_client import Neo4jClient
from app.retrieval.graph_search import GraphNeighbors, GraphSearchEngine
from app.retrieval.keyword_search import KeywordSearchEngine
from app.retrieval.semantic_search import SemanticSearchEngine


class HybridSearchResult(BaseModel):
    """Consolidated entity retrieved across semantic, keyword, and graph channels."""

    id: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    source: str
    final_score: float = Field(description="Combined ranking score")
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    graph_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    graph_context: Optional[GraphNeighbors] = None


class HybridSearchEngine:
    """
    Combines semantic code search, exact keyword matching, and graph relationship expansion.
    Formula: Score = weight_s * S + weight_g * G + weight_k * K
    Default weights: 0.60 Semantic, 0.25 Graph, 0.15 Keyword
    """

    def __init__(
        self,
        client: Optional[Neo4jClient] = None,
        embedder: Optional[CodeEmbedder] = None,
        weight_semantic: float = 0.60,
        weight_graph: float = 0.25,
        weight_keyword: float = 0.15,
    ) -> None:
        self.client = client
        self.embedder = embedder or CodeEmbedder()
        self.semantic_engine = SemanticSearchEngine(client=client, embedder=self.embedder)
        self.keyword_engine = KeywordSearchEngine(client=client)
        self.graph_engine = GraphSearchEngine(client=client)

        self.w_s = weight_semantic
        self.w_g = weight_graph
        self.w_k = weight_keyword

    def search(
        self,
        query: str,
        limit: int = 5,
        repo_id: Optional[str] = None,
    ) -> list[HybridSearchResult]:
        """Executes hybrid multi-channel search and returns unified ranked entities."""
        # 1. Channel A: Semantic Retrieval
        semantic_results = self.semantic_engine.search(query, limit=limit * 2, repo_id=repo_id)

        # 2. Channel B: Keyword Retrieval
        keyword_results = self.keyword_engine.search(query, limit=limit * 2, repo_id=repo_id)

        # Merge candidate entities by ID
        candidates: dict[str, dict[str, Any]] = {}

        for sr in semantic_results:
            candidates[sr.id] = {
                "entity": sr,
                "s_score": max(0.0, min(1.0, sr.score)),
                "k_score": 0.0,
                "reasons": [f"Semantic similarity ({sr.score:.2f})"],
            }

        for kr in keyword_results:
            if kr.id in candidates:
                candidates[kr.id]["k_score"] = kr.score
                candidates[kr.id]["reasons"].append(f"Keyword match '{kr.name}' ({kr.score:.2f})")
            else:
                candidates[kr.id] = {
                    "entity": kr,
                    "s_score": 0.0,
                    "k_score": kr.score,
                    "reasons": [f"Keyword match '{kr.name}' ({kr.score:.2f})"],
                }

        # 3. Channel C: Graph Neighborhood Expansion
        merged_results: list[HybridSearchResult] = []
        for entity_id, data in candidates.items():
            ent = data["entity"]
            s_score = data["s_score"]
            k_score = data["k_score"]

            graph_nbrs = self.graph_engine.get_neighborhood(entity_id)
            g_score = graph_nbrs.graph_relevance

            if graph_nbrs.relationship_summary:
                data["reasons"].extend(graph_nbrs.relationship_summary)

            final_score = (self.w_s * s_score) + (self.w_g * g_score) + (self.w_k * k_score)

            merged_results.append(
                HybridSearchResult(
                    id=ent.id,
                    name=ent.name,
                    qualified_name=ent.qualified_name,
                    file_path=ent.file_path,
                    start_line=ent.start_line,
                    end_line=ent.end_line,
                    signature=ent.signature,
                    docstring=ent.docstring,
                    source=ent.source,
                    final_score=round(final_score, 4),
                    semantic_score=round(s_score, 4),
                    keyword_score=round(k_score, 4),
                    graph_score=round(g_score, 4),
                    reasons=data["reasons"],
                    graph_context=graph_nbrs,
                )
            )

        merged_results.sort(key=lambda r: r.final_score, reverse=True)
        return merged_results[:limit]

    @classmethod
    def format_context_for_llm(cls, results: list[HybridSearchResult]) -> str:
        """
        Formats retrieved code entities into structured, citation-ready context for the LLM.
        Every code block carries verified file path and line numbers.
        """
        if not results:
            return "No relevant code context found."

        snippets: list[str] = []
        for idx, res in enumerate(results, start=1):
            reasons_str = "; ".join(res.reasons)
            loc = f"{res.file_path}:{res.start_line}-{res.end_line}"
            header = f"### Source {idx}: {loc} ({res.qualified_name})"
            meta = f"Score: {res.final_score:.2f} | Evidence: {reasons_str}"
            code_block = f"```{res.source}\n```"
            snippets.append(f"{header}\n{meta}\n{code_block}")

        return "\n\n".join(snippets)
