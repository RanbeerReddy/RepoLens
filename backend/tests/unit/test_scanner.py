"""Unit tests for RepositoryScanner."""

from pathlib import Path

from app.ingestion.scanner import RepositoryScanner


def test_scanner_discovers_python_files(tmp_path: Path):
    # Setup test structure
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "app" / "utils.py").write_text("def util(): pass", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")

    scanner = RepositoryScanner()
    scanned = scanner.scan(tmp_path)

    paths = [s.relative_path for s in scanned]
    assert "app/main.py" in paths
    assert "app/utils.py" in paths
    assert "README.md" not in paths
    assert "config.json" not in paths
    assert len(scanned) == 2


def test_scanner_ignores_standard_directories(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("code = 1", encoding="utf-8")

    # Ignored dirs
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hook.py").write_text("hook = 1", encoding="utf-8")

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("cached = 1", encoding="utf-8")

    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("lib = 1", encoding="utf-8")

    scanner = RepositoryScanner()
    scanned = scanner.scan(tmp_path)

    paths = [s.relative_path for s in scanned]
    assert paths == ["src/app.py"]


def test_scanner_respects_gitignore(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "included.py").write_text("a = 1", encoding="utf-8")
    (tmp_path / "app" / "ignored.py").write_text("b = 2", encoding="utf-8")
    (tmp_path / "temp").mkdir()
    (tmp_path / "temp" / "temp.py").write_text("c = 3", encoding="utf-8")

    (tmp_path / ".gitignore").write_text("ignored.py\ntemp/\n", encoding="utf-8")

    scanner = RepositoryScanner()
    scanned = scanner.scan(tmp_path)

    paths = [s.relative_path for s in scanned]
    assert paths == ["app/included.py"]


def test_scanner_computes_sha256(tmp_path: Path):
    file = tmp_path / "test.py"
    file.write_text("print('stable')", encoding="utf-8")

    scanner = RepositoryScanner()
    scanned = scanner.scan(tmp_path)

    assert len(scanned) == 1
    assert len(scanned[0].file_hash) == 64  # SHA-256 hex string length
