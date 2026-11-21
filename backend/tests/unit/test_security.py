"""Unit tests for path validation and security."""

from pathlib import Path
import pytest

from app.core.errors import ValidationError
from app.core.security import is_safe_relative_path, sanitize_entity_id, validate_repo_path


def test_sanitize_entity_id():
    raw = "repo_1:dir/file.py:func:my_func<test>"
    sanitized = sanitize_entity_id(raw)
    assert "<" not in sanitized
    assert ">" not in sanitized


def test_is_safe_relative_path():
    base = Path("/safe/repo/root").resolve()
    target_safe = base / "pkg" / "module.py"
    target_traversal = base / ".." / "etc" / "passwd"

    assert is_safe_relative_path(base, target_safe) is True
    assert is_safe_relative_path(base, target_traversal) is False


def test_validate_repo_path_nonexistent():
    with pytest.raises(ValidationError):
        validate_repo_path("/nonexistent_path_123456789")
