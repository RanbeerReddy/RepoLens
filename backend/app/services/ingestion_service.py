"""Repository ingestion service – parse, build graph, generate embeddings."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.core.errors import IngestionError

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.embeddings.generator import EmbeddingGenerator
    from app.graph.operations import GraphOperations

logger = logging.getLogger(__name__)

# File extensions considered as Python source
_PYTHON_EXTENSIONS: set[str] = {".py", ".pyi"}


class IngestionResult(BaseModel):
    """Summary of a repository ingestion run."""

    repo_id: str
    total_files: int = 0
    parsed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    functions_found: int = 0
    classes_found: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class IngestionService:
    """Orchestrates file discovery, parsing, graph building, and embedding generation."""

    def __init__(
        self,
        graph_ops: GraphOperations,
        embedding_generator: EmbeddingGenerator,
        settings: Settings,
    ) -> None:
        self.graph_ops = graph_ops
        self.embedding_generator = embedding_generator
        self.settings = settings

    async def ingest_repository(
        self, repo_id: str, repo_path: str
    ) -> IngestionResult:
        """Ingest (or re-ingest) a repository.

        1. Discover Python files.
        2. Compare ``source_hash`` to detect changes.
        3. Parse changed files and build/update graph nodes & edges.
        4. Generate embeddings for new/changed entities.
        5. Remove entities belonging to deleted files.

        Parameters
        ----------
        repo_id:
            Unique identifier of the repository node in the graph.
        repo_path:
            Absolute path to the repository root on disk.

        Returns
        -------
        IngestionResult
        """
        start = time.monotonic()
        result = IngestionResult(repo_id=repo_id)

        repo_root = Path(repo_path)
        if not repo_root.is_dir():
            raise IngestionError(
                message=f"Repository path does not exist: {repo_path}",
                details={"repo_id": repo_id, "path": repo_path},
            )

        # --- 1. Discover files ------------------------------------------------
        discovered_files = self._discover_files(repo_root)
        result.total_files = len(discovered_files)
        logger.info(
            "Repo %s: discovered %d Python files in %s",
            repo_id,
            result.total_files,
            repo_path,
        )

        # --- 2. Determine changed / new / deleted files -----------------------
        existing_hashes = await self._get_existing_hashes(repo_id)
        discovered_rel_paths: set[str] = set()

        files_to_parse: list[tuple[Path, str]] = []  # (abs_path, rel_path)

        for abs_path in discovered_files:
            rel_path = str(abs_path.relative_to(repo_root))
            discovered_rel_paths.add(rel_path)

            current_hash = self._hash_file(abs_path)
            if current_hash and existing_hashes.get(rel_path) == current_hash:
                result.skipped_files += 1
                continue

            files_to_parse.append((abs_path, rel_path))

        # --- 3. Parse changed files & build graph -----------------------------
        from app.parser.python_parser import PythonParser  # local import to avoid circular

        parser = PythonParser()

        for abs_path, rel_path in files_to_parse:
            try:
                source_code = abs_path.read_text(encoding="utf-8", errors="replace")
                source_hash = self._hash_content(source_code)

                parsed_module = parser.parse(
                    source=source_code,
                    file_path=rel_path,
                    repo_id=repo_id,
                )

                # Store nodes & relationships in graph
                await self.graph_ops.upsert_module(
                    repo_id=repo_id,
                    module=parsed_module,
                    source_hash=source_hash,
                )

                result.parsed_files += 1
                result.functions_found += len(parsed_module.functions)
                result.classes_found += len(parsed_module.classes)
                for cls in parsed_module.classes:
                    result.functions_found += len(cls.methods)

            except Exception as exc:
                result.failed_files += 1
                error_msg = f"{rel_path}: {exc}"
                result.errors.append(error_msg)
                logger.warning("Failed to parse %s: %s", rel_path, exc)

        # --- 4. Generate embeddings for new/changed entities ------------------
        try:
            await self._generate_embeddings(repo_id)
        except Exception as exc:
            error_msg = f"Embedding generation error: {exc}"
            result.errors.append(error_msg)
            logger.warning(error_msg)

        # --- 5. Remove deleted files ------------------------------------------
        deleted_paths = set(existing_hashes.keys()) - discovered_rel_paths
        for deleted_path in deleted_paths:
            try:
                await self.graph_ops.remove_file_entities(
                    repo_id=repo_id, file_path=deleted_path
                )
                logger.info("Removed entities for deleted file: %s", deleted_path)
            except Exception as exc:
                error_msg = f"Failed to clean up {deleted_path}: {exc}"
                result.errors.append(error_msg)
                logger.warning(error_msg)

        result.duration_seconds = round(time.monotonic() - start, 2)
        logger.info(
            "Repo %s ingestion complete: %d parsed, %d skipped, %d failed in %.1fs",
            repo_id,
            result.parsed_files,
            result.skipped_files,
            result.failed_files,
            result.duration_seconds,
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _discover_files(self, root: Path) -> list[Path]:
        """Recursively find Python files, respecting size limits."""
        max_file_kb = getattr(self.settings, "MAX_FILE_SIZE_KB", 1024)
        max_files = getattr(self.settings, "MAX_FILES", 10_000)
        files: list[Path] = []

        skip_dirs = {
            ".git", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
            "node_modules", ".venv", "venv", "env", ".eggs", "dist", "build",
        }

        for path in root.rglob("*"):
            if len(files) >= max_files:
                logger.warning("Hit MAX_FILES limit (%d)", max_files)
                break

            # Skip hidden / unneeded directories
            if any(part in skip_dirs for part in path.parts):
                continue

            if path.is_file() and path.suffix in _PYTHON_EXTENSIONS:
                try:
                    size_kb = path.stat().st_size / 1024
                    if size_kb <= max_file_kb:
                        files.append(path)
                except OSError:
                    continue

        return files

    async def _get_existing_hashes(self, repo_id: str) -> dict[str, str]:
        """Return ``{relative_path: source_hash}`` for already-ingested files."""
        try:
            return await self.graph_ops.get_file_hashes(repo_id)
        except Exception:
            logger.debug("Could not fetch existing hashes for repo %s", repo_id)
            return {}

    async def _generate_embeddings(self, repo_id: str) -> None:
        """Generate and store embeddings for entities missing them."""
        entities = await self.graph_ops.get_entities_without_embeddings(repo_id)
        if not entities:
            return

        texts = [
            self._entity_to_embedding_text(e) for e in entities
        ]
        embeddings = await self.embedding_generator.generate_batch(texts)

        for entity, embedding in zip(entities, embeddings):
            await self.graph_ops.set_embedding(
                entity_id=entity["entity_id"],
                embedding=embedding,
            )

        logger.info("Generated embeddings for %d entities in repo %s", len(entities), repo_id)

    @staticmethod
    def _entity_to_embedding_text(entity: dict) -> str:
        """Build a textual representation of an entity for embedding."""
        parts: list[str] = []
        if entity.get("entity_type"):
            parts.append(entity["entity_type"])
        if entity.get("qualified_name"):
            parts.append(entity["qualified_name"])
        if entity.get("docstring"):
            parts.append(entity["docstring"])
        if entity.get("source"):
            parts.append(entity["source"][:1000])
        return " ".join(parts) if parts else entity.get("name", "")

    @staticmethod
    def _hash_file(path: Path) -> str | None:
        """Return SHA-256 hex-digest of a file, or None on error."""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None

    @staticmethod
    def _hash_content(content: str) -> str:
        """Return SHA-256 hex-digest of a string."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
