"""Code embedding generator using Hugging Face sentence-transformers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from app.core.config import settings

if TYPE_CHECKING:
    from app.parser.models import ClassEntity, FunctionEntity


class CodeEmbedder:
    """Lazy-loading code embedder producing normalized semantic vectors."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model: Any = None
        self._dimension = 384  # Default for BAAI/bge-small-en-v1.5

    @property
    def model(self) -> Any:
        """Lazily instantiates the SentenceTransformer model on first access."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self._dimension = self._model.get_embedding_dimension()
            else:
                self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Batch-embeds a list of text strings into normalized float vectors."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embeds a single query string."""
        return self.embed_texts([query])[0]

    @staticmethod
    def format_function(fn: FunctionEntity) -> str:
        """Formats a function entity with structured metadata for semantic encoding."""
        doc = f"\nDocstring: {fn.docstring}" if fn.docstring else ""
        return (
            f"Function: {fn.name} in {fn.file_path}\n"
            f"Signature: {fn.signature}{doc}\n"
            f"Code:\n{fn.source}"
        )

    @staticmethod
    def format_class(cls: ClassEntity) -> str:
        """Formats a class entity with bases and docstring for semantic encoding."""
        bases = f" (inherits: {', '.join(cls.bases)})" if cls.bases else ""
        doc = f"\nDocstring: {cls.docstring}" if cls.docstring else ""
        methods = f"\nMethods: {', '.join(m.name for m in cls.methods)}" if cls.methods else ""
        return f"Class: {cls.name} in {cls.file_path}{bases}{doc}{methods}"
