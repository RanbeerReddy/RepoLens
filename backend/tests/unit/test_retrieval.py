"""Unit tests for Keyword, Graph, and Hybrid Retrieval Engines."""

from unittest.mock import MagicMock

import pytest

from app.embeddings.embedder import CodeEmbedder
from app.graph.neo4j_client import Neo4jClient
from app.retrieval.graph_search import GraphNeighbors, GraphSearchEngine
from app.retrieval.hybrid_search import HybridSearchEngine, HybridSearchResult
from app.retrieval.keyword_search import KeywordResult, KeywordSearchEngine
from app.retrieval.semantic_search import SearchResult


def test_keyword_search_scoring_and_ranking():
    candidates = [
        {
            "id": "fn:1",
            "name": "authenticate_user",
            "qualified_name": "app.auth.authenticate_user",
            "file_path": "app/auth.py",
            "start_line": 10,
            "end_line": 25,
            "signature": "def authenticate_user()",
            "source": "def authenticate_user(): pass",
        },
        {
            "id": "fn:2",
            "name": "user_profile",
            "qualified_name": "app.routes.user_profile",
            "file_path": "app/routes.py",
            "start_line": 5,
            "end_line": 15,
            "signature": "def user_profile()",
            "source": "def user_profile(): pass",
        },
    ]

    # Exact match query
    results = KeywordSearchEngine.search_in_memory("authenticate_user", candidates)
    assert len(results) == 1
    assert results[0].name == "authenticate_user"
    assert results[0].score == 1.0


def test_keyword_identifier_extraction():
    tokens = KeywordSearchEngine._extract_identifiers(
        "where is authenticate_user defined in the app?"
    )
    assert "authenticate_user" in tokens
    assert "where" not in tokens
    assert "is" not in tokens
    assert "the" not in tokens


def test_graph_neighborhood_in_memory():
    calls_graph = {
        "func:login": ["authenticate_user", "render_page"],
        "func:authenticate_user": ["verify_password", "get_user"],
    }
    candidates_by_name = {
        "authenticate_user": "func:authenticate_user",
        "verify_password": "func:verify_password",
    }

    nbrs = GraphSearchEngine.get_neighborhood_in_memory(
        "func:authenticate_user", calls_graph, candidates_by_name
    )
    assert len(nbrs.callees) == 2
    assert any(c["name"] == "verify_password" for c in nbrs.callees)
    assert len(nbrs.callers) == 1
    assert nbrs.callers[0]["name"] == "login"
    assert nbrs.graph_relevance > 0.0


def test_hybrid_search_ranking_formula():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_embedder = MagicMock(spec=CodeEmbedder)

    engine = HybridSearchEngine(
        client=mock_client,
        embedder=mock_embedder,
        weight_semantic=0.60,
        weight_graph=0.25,
        weight_keyword=0.15,
    )

    # Mock Semantic Channel
    engine.semantic_engine.search = MagicMock(
        return_value=[
            SearchResult(
                id="fn:auth",
                name="authenticate_user",
                qualified_name="app.auth.authenticate_user",
                file_path="app/auth.py",
                start_line=10,
                end_line=25,
                signature="def authenticate_user()",
                source="def authenticate_user(): pass",
                score=0.90,  # S = 0.90
            )
        ]
    )

    # Mock Keyword Channel
    engine.keyword_engine.search = MagicMock(
        return_value=[
            KeywordResult(
                id="fn:auth",
                name="authenticate_user",
                qualified_name="app.auth.authenticate_user",
                file_path="app/auth.py",
                start_line=10,
                end_line=25,
                signature="def authenticate_user()",
                source="def authenticate_user(): pass",
                score=1.0,  # K = 1.0
            )
        ]
    )

    # Mock Graph Channel
    engine.graph_engine.get_neighborhood = MagicMock(
        return_value=GraphNeighbors(
            function_id="fn:auth",
            callers=[{"name": "login", "id": "fn:login"}],
            callees=[{"name": "verify_password", "id": "fn:verify"}],
            graph_relevance=0.50,  # G = 0.50
            relationship_summary=["Called by: login", "Calls: verify_password"],
        )
    )

    results = engine.search("authenticate user credentials", limit=1)

    assert len(results) == 1
    res = results[0]
    assert res.name == "authenticate_user"
    assert res.semantic_score == 0.90
    assert res.keyword_score == 1.0
    assert res.graph_score == 0.50

    # Expected: 0.60 * 0.90 + 0.25 * 0.50 + 0.15 * 1.0 = 0.54 + 0.125 + 0.15 = 0.815
    assert pytest.approx(res.final_score, 0.001) == 0.815
    assert any("Semantic similarity" in r for r in res.reasons)
    assert any("Keyword match" in r for r in res.reasons)
    assert any("Called by: login" in r for r in res.reasons)


def test_format_context_for_llm():
    results = [
        HybridSearchResult(
            id="fn:auth",
            name="authenticate_user",
            qualified_name="app.auth.authenticate_user",
            file_path="app/auth.py",
            start_line=10,
            end_line=20,
            signature="def authenticate_user(email, password)",
            source="def authenticate_user(email, password):\n    return verify(password)",
            final_score=0.85,
            reasons=["Semantic match", "Called by: login"],
        )
    ]
    formatted = HybridSearchEngine.format_context_for_llm(results)
    assert "### Source 1: app/auth.py:10-20 (app.auth.authenticate_user)" in formatted
    assert "Score: 0.85" in formatted
    assert "Evidence: Semantic match; Called by: login" in formatted
    assert "def authenticate_user(email, password):" in formatted
