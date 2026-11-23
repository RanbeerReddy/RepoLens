"""Data models for extracted code entities in RepoLens."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class CallSite(BaseModel):
    """Represents a function or method call occurrence within a code block."""

    callee_name: str = Field(description="Name of the called function or method identifier")
    raw_expression: str = Field(description="Full call expression, e.g. 'self.verify_password'")
    line_number: int = Field(description="1-based line number where call occurs")
    is_method_call: bool = Field(default=False, description="Whether call is invoked on an object")


class ImportEntity(BaseModel):
    """Represents an imported module or imported names."""

    module: Optional[str] = Field(default=None, description="Imported module, e.g. 'os.path'")
    names: list[str] = Field(
        default_factory=list, description="Specific imported names, e.g. ['Session', 'select']"
    )
    alias_map: dict[str, str] = Field(
        default_factory=dict, description="Alias mappings, e.g. {'np': 'numpy'}"
    )
    is_relative: bool = Field(default=False, description="Whether import uses relative dot syntax")
    level: int = Field(default=0, description="Relative import level (number of leading dots)")
    start_line: int = Field(description="1-based line number of import statement")


class FunctionEntity(BaseModel):
    """Represents a Python function or class method."""

    id: str = Field(description="Stable entity identifier (e.g. func:path:class:name)")
    name: str = Field(description="Bare function name")
    qualified_name: str = Field(
        description="Fully qualified name, e.g. 'app.core.auth.authenticate_user'"
    )
    file_path: str = Field(description="Normalized relative file path with forward slashes")
    signature: str = Field(
        description="Normalized function signature with arguments and return type"
    )
    docstring: Optional[str] = Field(default=None, description="Cleaned docstring if present")
    source: str = Field(description="Complete source code snippet of the function")
    start_line: int = Field(description="1-based start line number")
    end_line: int = Field(description="1-based end line number")
    calls: list[str] = Field(
        default_factory=list, description="Distinct names of functions/methods called"
    )
    call_sites: list[CallSite] = Field(default_factory=list, description="Detailed call locations")
    decorators: list[str] = Field(
        default_factory=list, description="Decorators applied to this function"
    )
    parameters: list[str] = Field(default_factory=list, description="Parameter names in order")
    return_type: Optional[str] = Field(
        default=None, description="Return type annotation string if available"
    )
    is_async: bool = Field(default=False, description="True if async def")
    is_method: bool = Field(default=False, description="True if defined inside a class")
    class_name: Optional[str] = Field(
        default=None, description="Parent class name if this is a method"
    )


class ClassEntity(BaseModel):
    """Represents a Python class definition."""

    id: str = Field(description="Stable entity identifier (e.g. class:path:name)")
    name: str = Field(description="Bare class name")
    qualified_name: str = Field(description="Fully qualified name, e.g. 'app.models.User'")
    file_path: str = Field(description="Normalized relative file path with forward slashes")
    docstring: Optional[str] = Field(default=None, description="Cleaned docstring if present")
    start_line: int = Field(description="1-based start line number")
    end_line: int = Field(description="1-based end line number")
    bases: list[str] = Field(default_factory=list, description="Direct base class names")
    methods: list[FunctionEntity] = Field(
        default_factory=list, description="Methods defined in this class"
    )
    decorators: list[str] = Field(
        default_factory=list, description="Decorators applied to this class"
    )


class ParsedFile(BaseModel):
    """Represents a parsed Python source file."""

    id: str = Field(description="Stable entity identifier (e.g. file:relative_path)")
    file_path: str = Field(description="Normalized relative file path with forward slashes")
    file_hash: str = Field(description="SHA-256 hash of file contents")
    size_bytes: int = Field(description="File size in bytes")
    total_lines: int = Field(description="Total line count")
    docstring: Optional[str] = Field(default=None, description="Module-level docstring if present")
    imports: list[ImportEntity] = Field(default_factory=list, description="Imports in this file")
    classes: list[ClassEntity] = Field(
        default_factory=list, description="Classes defined in this file"
    )
    functions: list[FunctionEntity] = Field(
        default_factory=list, description="Top-level functions in this file"
    )
    syntax_valid: bool = Field(
        default=True, description="False if file had syntax errors during parsing"
    )
    error_message: Optional[str] = Field(
        default=None, description="Parsing error message if invalid"
    )

    def get_all_functions(self) -> list[FunctionEntity]:
        """Returns both top-level functions and all class methods."""
        all_funcs: list[FunctionEntity] = list(self.functions)
        for cls in self.classes:
            all_funcs.extend(cls.methods)
        return all_funcs


class ParsedRepository(BaseModel):
    """Represents an entire parsed repository."""

    root_path: str = Field(description="Absolute path to the repository root")
    repo_name: str = Field(description="Repository name or directory basename")
    files: list[ParsedFile] = Field(default_factory=list, description="All parsed Python files")
    total_files: int = Field(default=0, description="Total number of scanned python files")
    total_functions: int = Field(
        default=0, description="Total functions across all files including methods"
    )
    total_classes: int = Field(default=0, description="Total classes across all files")
    total_lines: int = Field(default=0, description="Total lines of Python code")

    def to_summary_dict(self) -> list[dict[str, Any]]:
        """
        Produces clean structured JSON matching the Phase 1 deliverable specification:
        [
          {
            "file": "app/auth.py",
            "functions": [
              {
                "name": "authenticate_user",
                "start_line": 10,
                "end_line": 25,
                "calls": ["verify_password", "get_user_by_email"]
              }
            ]
          }
        ]
        """
        result: list[dict[str, Any]] = []
        for file in self.files:
            file_entry: dict[str, Any] = {
                "file": file.file_path,
                "functions": [
                    {
                        "name": fn.name,
                        "qualified_name": fn.qualified_name,
                        "start_line": fn.start_line,
                        "end_line": fn.end_line,
                        "calls": fn.calls,
                        "is_method": fn.is_method,
                        "class_name": fn.class_name,
                    }
                    for fn in file.get_all_functions()
                ],
                "classes": [
                    {
                        "name": cls.name,
                        "start_line": cls.start_line,
                        "end_line": cls.end_line,
                        "bases": cls.bases,
                    }
                    for cls in file.classes
                ],
            }
            result.append(file_entry)
        return result

    def to_summary_json(self, indent: int = 2) -> str:
        """Serializes the summary structure to formatted JSON."""
        return json.dumps(self.to_summary_dict(), indent=indent)
