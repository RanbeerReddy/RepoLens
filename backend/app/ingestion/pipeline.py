"""Repository Ingestion Pipeline.

Combines directory scanning and AST parsing to extract an entire repository
into a structured ParsedRepository object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.ingestion.scanner import RepositoryScanner, ScannedFile
from app.parser.ast_parser import PythonASTParser
from app.parser.models import ParsedFile, ParsedRepository


class IngestionPipeline:
    """Orchestrates code scanning and AST entity extraction across a repository."""

    def __init__(
        self,
        max_file_size_bytes: int = 512 * 1024,
        max_files: int = 10000,
        extra_ignores: Optional[list[str]] = None,
    ) -> None:
        self.scanner = RepositoryScanner(
            max_file_size_bytes=max_file_size_bytes,
            max_files=max_files,
            extra_ignores=extra_ignores,
        )

    def parse_repository(
        self, repo_path: str | Path, repo_name: Optional[str] = None
    ) -> ParsedRepository:
        """
        Scans and parses all eligible Python files in repo_path.

        Args:
            repo_path: Directory path of the Python repository
            repo_name: Optional human-readable repository name (defaults to folder name)

        Returns:
            ParsedRepository populated with all parsed files and summary statistics
        """
        root = Path(repo_path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Target repository path is not a directory: {root}")

        name = repo_name or root.name
        ast_parser = PythonASTParser(repo_name=name)

        scanned_files = self.scanner.scan(root)
        parsed_files: list[ParsedFile] = []

        total_lines = 0
        total_functions = 0
        total_classes = 0

        for item in scanned_files:
            parsed_file = self._process_file(item, ast_parser)
            parsed_files.append(parsed_file)

            total_lines += parsed_file.total_lines
            total_functions += len(parsed_file.get_all_functions())
            total_classes += len(parsed_file.classes)

        return ParsedRepository(
            root_path=str(root),
            repo_name=name,
            files=parsed_files,
            total_files=len(parsed_files),
            total_functions=total_functions,
            total_classes=total_classes,
            total_lines=total_lines,
        )

    def _process_file(self, item: ScannedFile, parser: PythonASTParser) -> ParsedFile:
        """Reads file text safely and invokes the AST parser."""
        file_path = Path(item.absolute_path)
        try:
            source_code = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as err:
            return ParsedFile(
                id=f"file:{item.relative_path}",
                file_path=item.relative_path,
                file_hash=item.file_hash,
                size_bytes=item.size_bytes,
                total_lines=0,
                syntax_valid=False,
                error_message=f"File read error: {str(err)}",
            )

        return parser.parse_file(
            file_path=item.relative_path,
            source_code=source_code,
            file_hash=item.file_hash,
        )

    @classmethod
    def parse_to_json(
        cls,
        repo_path: str | Path,
        repo_name: Optional[str] = None,
        indent: int = 2,
    ) -> str:
        """
        Convenience method to parse repository and return formatted JSON
        satisfying the Phase 1 deliverable format.
        """
        pipeline = cls()
        parsed_repo = pipeline.parse_repository(repo_path, repo_name)
        return parsed_repo.to_summary_json(indent=indent)

    @classmethod
    def parse_to_dict(
        cls,
        repo_path: str | Path,
        repo_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Convenience method returning the structured dictionary format.
        """
        pipeline = cls()
        parsed_repo = pipeline.parse_repository(repo_path, repo_name)
        return parsed_repo.to_summary_dict()
