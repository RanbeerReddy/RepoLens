"""Path-safety and sanitisation utilities."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.errors import ValidationError

# Directories that must never be treated as a repository root.
_SYSTEM_DIRS: frozenset[str] = frozenset(
    {"/etc", "/usr", "/var", "/proc", "/sys", "/dev", "/root", "/boot"}
)

# The RepoLens application directory (resolved once at import time).
_APP_DIR: Path = Path(__file__).resolve().parents[2]  # …/backend/app -> …/backend


def validate_repo_path(path: str) -> Path:
    """Resolve *path* and validate it is a safe repository directory.

    Raises
    ------
    ValidationError
        If the path does not exist, is not a directory, points to a system
        directory, or is located inside the RepoLens application tree.

    Returns
    -------
    Path
        The resolved, validated :class:`~pathlib.Path`.
    """
    resolved = Path(path).resolve()

    if not resolved.exists():
        raise ValidationError(f"Path does not exist: {resolved}")

    if not resolved.is_dir():
        raise ValidationError(f"Path is not a directory: {resolved}")

    # Reject system directories (exact match or descendant).
    for sys_dir in _SYSTEM_DIRS:
        sys_path = Path(sys_dir)
        if resolved == sys_path or sys_path in resolved.parents:
            raise ValidationError(
                f"Path is inside a restricted system directory: {resolved}",
                details={"system_dir": sys_dir},
            )

    # Reject paths inside the RepoLens application itself.
    if resolved == _APP_DIR or _APP_DIR in resolved.parents or resolved in _APP_DIR.parents:
        # resolved is *inside* the app dir, or *is* the app dir
        pass  # only block if resolved is inside _APP_DIR
    if resolved == _APP_DIR or _APP_DIR == resolved or str(resolved).startswith(str(_APP_DIR)):
        raise ValidationError(
            "Path is inside the RepoLens application directory",
            details={"app_dir": str(_APP_DIR)},
        )

    return resolved


def is_safe_relative_path(base: Path, target: Path) -> bool:
    """Return ``True`` if *target* resolves to a location inside *base*.

    This guards against path-traversal attacks (e.g. ``../../etc/passwd``).
    """
    try:
        resolved_base = base.resolve()
        resolved_target = target.resolve()
        # The target must start with (or equal) the base directory.
        resolved_target.relative_to(resolved_base)
        return True
    except ValueError:
        return False


def sanitize_entity_id(raw: str) -> str:
    """Strip characters that could be dangerous in an entity identifier.

    Only alphanumerics, hyphens, underscores, dots, colons, and forward
    slashes are retained.
    """
    return re.sub(r"[^a-zA-Z0-9_\-\.:/]", "", raw)
