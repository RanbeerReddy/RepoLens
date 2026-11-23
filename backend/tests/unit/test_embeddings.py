"""Unit tests for CodeEmbedder."""

from unittest.mock import MagicMock

import numpy as np

from app.embeddings.embedder import CodeEmbedder
from app.parser.models import ClassEntity, FunctionEntity


def test_format_function():
    fn = FunctionEntity(
        id="func:test:1",
        name="authenticate_user",
        qualified_name="app.auth.authenticate_user",
        file_path="app/auth.py",
        signature="def authenticate_user(email: str, password: str) -> bool",
        docstring="Authenticates user by email and password.",
        source="def authenticate_user(email, password):\n    return check(email, password)",
        start_line=10,
        end_line=12,
    )
    formatted = CodeEmbedder.format_function(fn)
    assert "Function: authenticate_user in app/auth.py" in formatted
    assert "Signature: def authenticate_user" in formatted
    assert "Docstring: Authenticates user by email" in formatted
    assert "Code:\ndef authenticate_user" in formatted


def test_format_class():
    cls = ClassEntity(
        id="class:test:1",
        name="UserService",
        qualified_name="app.services.UserService",
        file_path="app/services.py",
        docstring="Manages users.",
        start_line=1,
        end_line=20,
        bases=["BaseService"],
    )
    formatted = CodeEmbedder.format_class(cls)
    assert "Class: UserService in app/services.py" in formatted
    assert "inherits: BaseService" in formatted
    assert "Docstring: Manages users." in formatted


def test_embed_texts_with_mocked_model():
    embedder = CodeEmbedder()
    # Mock underlying SentenceTransformer to avoid heavyweight download in unit tests
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32)
    mock_model.get_sentence_embedding_dimension.return_value = 3
    embedder._model = mock_model

    vectors = embedder.embed_texts(["hello", "world"])
    assert len(vectors) == 2
    assert vectors[0] == [0.10000000149011612, 0.20000000298023224, 0.30000001192092896]
    mock_model.encode.assert_called_once()


def test_embed_empty_list():
    embedder = CodeEmbedder()
    assert embedder.embed_texts([]) == []
