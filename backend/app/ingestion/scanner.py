"""Repository file scanner with .gitignore and standard ignore support."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import pathspec
from pydantic import BaseModel


class ScannedFile(BaseModel):
    """Metadata for a discovered Python source file."""

    relative_path: str
    absolute_path: str
    size_bytes: int
    file_hash: str


class RepositoryScanner:
    """Discovers and filters Python files in a target directory."""

    DEFAULT_IGNORED_DIRS: set[str] = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "node_modules",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".idea",
        ".vscode",
    }

    DEFAULT_IGNORED_EXTENSIONS: set[str] = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dll",
        ".dylib",
    }

    def __init__(
        self,
        max_file_size_bytes: int = 512 * 1024,
        max_files: int = 10000,
        extra_ignores: Optional[list[str]] = None,
    ) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self.max_files = max_files
        self.extra_ignores = extra_ignores or []

    def scan(self, root_path: str | Path) -> list[ScannedFile]:
        """
        Recursively scans root_path for Python source files, applying ignore rules.

        Args:
            root_path: Root folder of the target repository

        Returns:
            List of ScannedFile objects sorted by relative path
        """
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Target repository path is not a directory: {root}")

        gitignore_spec = self._load_gitignore(root)
        discovered: list[ScannedFile] = []

        for item in self._walk_directory(root, gitignore_spec):
            if len(discovered) >= self.max_files:
                break
            discovered.append(item)

        discovered.sort(key=lambda f: f.relative_path)
        return discovered

    def _walk_directory(
        self,
        root: Path,
        gitignore_spec: Optional[pathspec.PathSpec],
    ) -> list[ScannedFile]:
        """Walks directory tree filtering out ignored items."""
        scanned: list[ScannedFile] = []

        for current_dir, dirnames, filenames in root.walk():
            # In-place filter out ignored directory names so os.walk does not descend into them
            dirnames[:] = [
                d
                for d in dirnames
                if not self._is_dir_ignored(d, current_dir / d, root, gitignore_spec)
            ]

            for filename in filenames:
                file_path = current_dir / filename
                if not self._is_file_candidate(filename, file_path, root, gitignore_spec):
                    continue

                try:
                    stat = file_path.stat()
                    size = stat.st_size
                    if size > self.max_file_size_bytes:
                        continue

                    rel_path = file_path.relative_to(root).as_posix()
                    file_hash = self._compute_sha256(file_path)

                    scanned.append(
                        ScannedFile(
                            relative_path=rel_path,
                            absolute_path=str(file_path),
                            size_bytes=size,
                            file_hash=file_hash,
                        )
                    )
                except (OSError, PermissionError):
                    # Gracefully skip inaccessible files
                    continue

        return scanned

    def _is_dir_ignored(
        self,
        dirname: str,
        dir_path: Path,
        root: Path,
        gitignore_spec: Optional[pathspec.PathSpec],
    ) -> bool:
        """Determines if a directory should be skipped."""
        if dirname in self.DEFAULT_IGNORED_DIRS:
            return True
        if dirname.startswith("."):
            return True
        if dirname.endswith(".egg-info"):
            return True

        if gitignore_spec:
            try:
                rel_dir = dir_path.relative_to(root).as_posix() + "/"
                if gitignore_spec.match_file(rel_dir):
                    return True
            except ValueError:
                pass

        return False

    def _is_file_candidate(
        self,
        filename: str,
        file_path: Path,
        root: Path,
        gitignore_spec: Optional[pathspec.PathSpec],
    ) -> bool:
        """Determines if a file is an eligible Python source file."""
        if not filename.endswith(".py"):
            return False

        if filename.startswith("."):
            return True

        if gitignore_spec:
            try:
                rel_file = file_path.relative_to(root).as_posix()
                if gitignore_spec.match_file(rel_file):
                    return False
            except ValueError:
                pass

        return True

    def _load_gitignore(self, root: Path) -> Optional[pathspec.PathSpec]:
        """Loads and compiles .gitignore from the root folder if present."""
        gitignore_file = root / ".gitignore"
        lines: list[str] = list(self.extra_ignores)

        if gitignore_file.is_file():
            try:
                content = gitignore_file.read_text(encoding="utf-8", errors="replace")
                lines.extend(content.splitlines())
            except Exception:
                pass

        if lines:
            return pathspec.PathSpec.from_lines("gitwildmatch", lines)
        return None

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        """Calculates SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
