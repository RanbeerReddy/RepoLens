"""Unit tests for SemanticSearchEngine."""

from unittest.mock import MagicMock

from app.embeddings.embedder import CodeEmbedder
from app.graph.neo4j_client import Neo4jClient
from app.retrieval.semantic_search import SemanticSearchEngine


def test_search_in_memory_ranks_by_similarity():
    # Query vector pointing towards dimension 0
    query_vector = [1.0, 0.0, 0.0]

    # Candidate 1: strong match along dimension 0
    # Candidate 2: orthogonal match along dimension 1
    candidates = [
        {
            "id": "func:1",
            "name": "login",
            "qualified_name": "app.auth.login",
            "file_path": "app/auth.py",
            "start_line": 5,
            "end_line": 15,
            "signature": "def login()",
            "docstring": "Logs in user",
            "source": "def login(): pass",
            "embedding": [0.95, 0.05, 0.0],
        },
        {
            "id": "func:2",
            "name": "render_view",
            "qualified_name": "app.ui.render_view",
            "file_path": "app/ui.py",
            "start_line": 20,
            "end_line": 30,
            "signature": "def render_view()",
            "docstring": "Renders UI HTML",
            "source": "def render_view(): pass",
            "embedding": [0.0, 1.0, 0.0],
        },
    ]

    results = SemanticSearchEngine.search_in_memory(query_vector, candidates, limit=2)
    assert len(results) == 2
    # Candidate 1 should be first because [0.95, 0.05] is closest to [1.0, 0.0]
    assert results[0].name == "login"
    assert results[0].score > 0.9
    assert results[1].name == "render_view"
    assert results[1].score < 0.1


def test_store_function_embeddings_executes_batch():
    mock_client = MagicMock(spec=Neo4jClient)
    engine = SemanticSearchEngine(client=mock_client)

    batch = [
        {"id": "func:1", "embedding": [0.1, 0.2]},
        {"id": "func:2", "embedding": [0.3, 0.4]},
    ]
    stored_count = engine.store_function_embeddings(batch)
    assert stored_count == 2
    mock_client.execute_write.assert_called_once()


def test_search_neo4j_calls_vector_query():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_client.execute_read.return_value = [
        {
            "id": "func:1",
            "name": "connect_db",
            "qualified_name": "app.db.connect_db",
            "file_path": "app/db.py",
            "start_line": 1,
            "end_line": 10,
            "signature": "def connect_db()",
            "docstring": "Initializes pool",
            "source": "def connect_db(): pass",
            "score": 0.88,
        }
    ]

    mock_embedder = MagicMock(spec=CodeEmbedder)
    mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3]

    engine = SemanticSearchEngine(client=mock_client, embedder=mock_embedder)
    results = engine.search("where is database connection initialized?", limit=5)

    assert len(results) == 1
    assert results[0].name == "connect_db"
    assert results[0].score == 0.88
    mock_embedder.embed_query.assert_called_once()
    mock_client.execute_read.assert_called_once()
