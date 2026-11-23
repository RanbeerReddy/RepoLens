"""Unit tests for ChatService."""

from unittest.mock import MagicMock

from app.llm.vllm_client import LLMError, VLLMClient
from app.retrieval.hybrid_search import HybridSearchEngine, HybridSearchResult
from app.services.chat_service import ChatService


def test_chat_service_success_with_citations():
    mock_retrieval = MagicMock(spec=HybridSearchEngine)
    mock_retrieval.search.return_value = [
        HybridSearchResult(
            id="fn:auth",
            name="authenticate_user",
            qualified_name="app.auth.authenticate_user",
            file_path="app/auth.py",
            start_line=20,
            end_line=42,
            signature="def authenticate_user()",
            source="def authenticate_user(): pass",
            final_score=0.92,
            reasons=["Semantic match (0.92)"],
        )
    ]

    mock_llm = MagicMock(spec=VLLMClient)
    mock_llm.generate.return_value = (
        "Authentication is handled by authenticate_user() in [app/auth.py:20-42]."
    )

    service = ChatService(retrieval_engine=mock_retrieval, llm_client=mock_llm)
    resp = service.ask("How does user auth work?")

    assert resp.llm_used is True
    assert "authenticate_user" in resp.answer
    assert len(resp.sources) == 1
    source = resp.sources[0]
    assert source.citation == "app/auth.py:20-42"
    assert source.qualified_name == "app.auth.authenticate_user"
    assert source.relevance_score == 0.92


def test_chat_service_empty_retrieval():
    mock_retrieval = MagicMock(spec=HybridSearchEngine)
    mock_retrieval.search.return_value = []
    mock_llm = MagicMock(spec=VLLMClient)

    service = ChatService(retrieval_engine=mock_retrieval, llm_client=mock_llm)
    resp = service.ask("Nonexistent function")

    assert resp.retrieved_count == 0
    assert resp.llm_used is False
    assert "No relevant code was found" in resp.answer
    mock_llm.generate.assert_not_called()


def test_chat_service_graceful_offline_degradation():
    mock_retrieval = MagicMock(spec=HybridSearchEngine)
    mock_retrieval.search.return_value = [
        HybridSearchResult(
            id="fn:db",
            name="init_db",
            qualified_name="app.db.init_db",
            file_path="app/db.py",
            start_line=5,
            end_line=15,
            signature="def init_db()",
            source="def init_db(): pass",
            final_score=0.85,
            reasons=["Exact match"],
        )
    ]

    mock_llm = MagicMock(spec=VLLMClient)
    mock_llm.generate.side_effect = LLMError("Connection to vLLM timed out")

    service = ChatService(retrieval_engine=mock_retrieval, llm_client=mock_llm)
    resp = service.ask("Where is db initialized?")

    # Service should not raise exception; instead, return retrieved evidence
    assert resp.llm_used is False
    assert "offline" in resp.answer.lower()
    assert len(resp.sources) == 1
    assert resp.sources[0].citation == "app/db.py:5-15"
