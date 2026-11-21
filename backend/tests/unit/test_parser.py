"""Unit tests for the Python AST Parser."""

import tempfile
from pathlib import Path

import pytest

from app.parser.ast_parser import PythonASTParser
from app.parser.file_discovery import discover_python_files


SAMPLE_CODE = '''"""Sample module docstring."""

import os
from pathlib import Path
from math import sqrt as square_root

GLOBAL_CONST = 42

def standalone_func(x: int, y: int = 10) -> int:
    """Computes a sum."""
    print("hello")
    res = square_root(x)
    return x + y

class Animal:
    """Base animal class."""
    species = "unknown"

    def __init__(self, name: str):
        self.name = name

    def speak(self) -> str:
        """Sound of animal."""
        return "..."

class Dog(Animal):
    """Dog subclass."""

    def speak(self) -> str:
        standalone_func(1, 2)
        return "woof"

    async def fetch(self, item: str):
        return f"fetching {item}"
'''


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        sub_dir = repo_path / "pkg"
        sub_dir.mkdir()

        file1 = sub_dir / "sample.py"
        file1.write_text(SAMPLE_CODE, encoding="utf-8")

        file2 = sub_dir / "empty.py"
        file2.write_text("", encoding="utf-8")

        yield repo_path


def test_discover_files(temp_repo):
    files = discover_python_files(temp_repo, max_files=100, max_file_size_kb=500)
    rel_paths = [f.relative_path for f in files]
    assert "pkg/sample.py" in rel_paths
    assert "pkg/empty.py" in rel_paths


def test_parse_sample_module(temp_repo):
    parser = PythonASTParser(repo_id="test_repo", repo_root=str(temp_repo))
    parsed = parser.parse_file("pkg/sample.py")

    assert parsed.error is None
    assert parsed.module_docstring == "Sample module docstring."
    assert len(parsed.imports) >= 3

    # Check functions
    func_names = [f.name for f in parsed.functions]
    assert "standalone_func" in func_names

    standalone = next(f for f in parsed.functions if f.name == "standalone_func")
    assert standalone.docstring == "Computes a sum."
    assert standalone.line_start > 0
    assert "x" in standalone.args

    # Check classes
    class_names = [c.name for c in parsed.classes]
    assert "Animal" in class_names
    assert "Dog" in class_names

    dog_class = next(c for c in parsed.classes if c.name == "Dog")
    assert "Animal" in dog_class.bases
    method_names = [m.name for m in dog_class.methods]
    assert "speak" in method_names
    assert "fetch" in method_names

    # Check async method
    fetch_method = next(m for m in dog_class.methods if m.name == "fetch")
    assert fetch_method.is_async is True


def test_parse_syntax_error(temp_repo):
    bad_file = temp_repo / "pkg" / "bad.py"
    bad_file.write_text("def broken_syntax( {", encoding="utf-8")

    parser = PythonASTParser(repo_id="test_repo", repo_root=str(temp_repo))
    parsed = parser.parse_file("pkg/bad.py")

    assert parsed.error is not None
    assert "SyntaxError" in parsed.error or "invalid syntax" in parsed.error.lower()
