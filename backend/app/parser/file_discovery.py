"""Discover Python source files in a repository, respecting .gitignore and size limits."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Directories that are always skipped regardless of .gitignore
SKIP_DIRS: set[str] = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".env",
}

# Also skip any directory whose name ends with this suffix
SKIP_DIR_SUFFIXES: tuple[str, ...] = ("egg-info",)


class DiscoveredFile(BaseModel):
    """A Python file found during repository scanning."""

    relative_path: str = Field(description="Path relative to the repository root")
    absolute_path: Path = Field(description="Fully-resolved absolute path")
    size_bytes: int = Field(ge=0)
    modified_time: float

    model_config = {"arbitrary_types_allowed": True}


def _load_gitignore_spec(repo_path: Path):  # type: ignore[return]
    """Try to load a ``pathspec.PathSpec`` from ``.gitignore``.

    Returns ``None`` when pathspec is not installed or the file is missing.
    """
    try:
        import pathspec  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("pathspec library not available – .gitignore will be ignored")
        return None

    gitignore = repo_path / ".gitignore"
    if not gitignore.is_file():
        return None

    try:
        text = gitignore.read_text(encoding="utf-8", errors="replace")
        return pathspec.PathSpec.from_lines("gitwildmatch", text.splitlines())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse .gitignore: %s", exc)
        return None


def _should_skip_dir(dir_name: str) -> bool:
    if dir_name in SKIP_DIRS:
        return True
    for suffix in SKIP_DIR_SUFFIXES:
        if dir_name.endswith(suffix):
            return True
    return False


def _is_likely_binary(path: Path) -> bool:
    """Quick heuristic: read first 8 KiB and look for null bytes."""
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


def discover_python_files(
    repo_path: Path,
    max_files: int = 10_000,
    max_file_size_kb: int = 500,
) -> list[DiscoveredFile]:
    """Walk *repo_path* and return a sorted list of Python source files.

    Parameters
    ----------
    repo_path:
        Root of the repository to scan.
    max_files:
        Stop after collecting this many files.
    max_file_size_kb:
        Skip files larger than this many kilobytes.
    """
    repo_path = repo_path.resolve()
    if not repo_path.is_dir():
        logger.error("Repository path does not exist or is not a directory: %s", repo_path)
        return []

    gitignore_spec = _load_gitignore_spec(repo_path)
    max_file_size_bytes = max_file_size_kb * 1024
    discovered: list[DiscoveredFile] = []

    dirs_to_walk: list[Path] = [repo_path]

    while dirs_to_walk:
        current_dir = dirs_to_walk.pop()

        try:
            entries = sorted(current_dir.iterdir(), key=lambda p: p.name)
        except PermissionError:
            logger.debug("Permission denied: %s", current_dir)
            continue

        subdirs: list[Path] = []
        for entry in entries:
            # --- directories ---------------------------------------------------
            if entry.is_dir():
                if _should_skip_dir(entry.name):
                    continue
                # Check .gitignore
                if gitignore_spec is not None:
                    try:
                        rel = str(entry.relative_to(repo_path)) + "/"
                        if gitignore_spec.match_file(rel):
                            continue
                    except ValueError:
                        pass
                subdirs.append(entry)
                continue

            # --- files ---------------------------------------------------------
            if not entry.is_file():
                continue

            # Skip hidden files
            if entry.name.startswith("."):
                continue

            # Only .py files
            if entry.suffix != ".py":
                continue

            # Size check
            try:
                stat = entry.stat()
            except OSError:
                continue
            if stat.st_size > max_file_size_bytes:
                logger.debug("Skipping oversized file: %s (%d bytes)", entry, stat.st_size)
                continue

            # Binary check
            if _is_likely_binary(entry):
                logger.debug("Skipping likely binary: %s", entry)
                continue

            # .gitignore check
            if gitignore_spec is not None:
                try:
                    rel = str(entry.relative_to(repo_path))
                    if gitignore_spec.match_file(rel):
                        continue
                except ValueError:
                    pass

            discovered.append(
                DiscoveredFile(
                    relative_path=str(entry.relative_to(repo_path)),
                    absolute_path=entry,
                    size_bytes=stat.st_size,
                    modified_time=stat.st_mtime,
                )
            )

            if len(discovered) >= max_files:
                logger.info(
                    "Reached max_files limit (%d) – stopping discovery", max_files
                )
                # Sort and return early
                discovered.sort(key=lambda f: f.relative_path)
                return discovered

        # Queue subdirs in sorted order (breadth-first, alphabetical within level)
        dirs_to_walk.extend(reversed(subdirs))

    discovered.sort(key=lambda f: f.relative_path)
    return discovered
