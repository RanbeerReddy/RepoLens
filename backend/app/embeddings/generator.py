"""Embedding generation using sentence-transformers models."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate vector embeddings from text using sentence-transformers.

    Loads the model lazily on first use. If sentence-transformers is not
    installed the generator remains in an unavailable state and all calls
    return empty results.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._model: Any = None
        self._available: bool = True  # optimistic until proven otherwise
        self._loaded: bool = False
        self._dimension: int | None = None

    # ------------------------------------------------------------------ #
    #  Model loading
    # ------------------------------------------------------------------ #

    def _load_model(self) -> None:
        """Lazy-load the sentence-transformers model.

        Sets ``self._available = False`` if the library is missing or the model
        cannot be loaded, so callers can check ``is_available()`` afterwards.
        """
        if self._loaded:
            return

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

            self._model = SentenceTransformer(
                self._model_name, device=self._device
            )
            self._dimension = self._model.get_sentence_embedding_dimension()
            self._loaded = True
            logger.info(
                "Loaded embedding model '%s' (dim=%d, device=%s)",
                self._model_name,
                self._dimension,
                self._device,
            )
        except ImportError:
            logger.warning(
                "sentence-transformers is not installed – embeddings unavailable. "
                "Install with: pip install sentence-transformers"
            )
            self._available = False
            self._loaded = True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load embedding model '%s': %s",
                self._model_name,
                exc,
            )
            self._available = False
            self._loaded = True

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        """Return *True* if the embedding model loaded successfully."""
        if not self._loaded:
            self._load_model()
        return self._available

    def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate normalised embeddings for a batch of texts.

        Long texts are automatically truncated by the underlying model's
        tokenizer.  Returns an empty list when the model is unavailable.
        """
        if not self.is_available():
            return []

        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Process in batches
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]

            # Encode returns numpy array of shape (batch, dim)
            raw: np.ndarray = self._model.encode(
                batch,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

            # Ensure normalisation (belt-and-suspenders)
            norms = np.linalg.norm(raw, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            normalised = raw / norms

            all_embeddings.extend(normalised.tolist())

        return all_embeddings

    def generate_single(self, text: str) -> list[float]:
        """Generate a normalised embedding for a single text.

        Returns an empty list when the model is unavailable.
        """
        results = self.generate([text])
        return results[0] if results else []

    def get_dimension(self) -> int:
        """Return the embedding dimensionality.

        Returns 0 when the model is unavailable.
        """
        if not self.is_available():
            return 0
        return self._dimension or 0
