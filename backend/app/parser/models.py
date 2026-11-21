"""Pydantic data models for parsed Python source entities."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedImport(BaseModel):
    """A single import statement extracted from a Python module."""

    module: str = Field(description="The module being imported")
    names: list[str] = Field(default_factory=list, description="Names imported from the module")
    alias: str | None = Field(default=None, description="Import alias (as …)")
    is_from: bool = Field(default=False, description="True for 'from X import Y' style")
    line_number: int = Field(description="Source line number")


class ParsedFunctionCall(BaseModel):
    """A function/method call site found inside a function body."""

    name: str = Field(description="Simple call name as it appears in source")
    qualified_name: str | None = Field(
        default=None,
        description="Fully-qualified name if resolvable, else None",
    )
    line_number: int = Field(description="Source line number of the call")
    context: str | None = Field(
        default=None,
        description="Enclosing function or class qualified name",
    )


class ParsedFunction(BaseModel):
    """A function or method extracted from the AST."""

    name: str
    qualified_name: str = Field(description="Dot-separated qualified name within the module")
    entity_id: str = Field(description="Global entity ID: repo_id:file_path:function:qname")
    file_path: str
    line_start: int
    line_end: int
    source: str = Field(description="Full source text of the function")
    signature: str = Field(description="Human-readable signature string")
    docstring: str | None = None
    decorators: list[str] = Field(default_factory=list)
    is_method: bool = False
    is_async: bool = False
    calls: list[ParsedFunctionCall] = Field(default_factory=list)
    args: list[str] = Field(default_factory=list)


class ParsedClass(BaseModel):
    """A class extracted from the AST."""

    name: str
    qualified_name: str
    entity_id: str = Field(description="Global entity ID: repo_id:file_path:class:qname")
    file_path: str
    line_start: int
    line_end: int
    source: str
    docstring: str | None = None
    decorators: list[str] = Field(default_factory=list)
    bases: list[str] = Field(default_factory=list)
    methods: list[ParsedFunction] = Field(default_factory=list)


class ParsedModule(BaseModel):
    """Complete parse result for a single Python source file."""

    file_path: str
    entity_id: str = Field(description="Global entity ID: repo_id:file_path:module:module_qname")
    repo_id: str
    source_hash: str = Field(description="SHA-256 hex digest of the file content")
    size_bytes: int
    imports: list[ParsedImport] = Field(default_factory=list)
    functions: list[ParsedFunction] = Field(default_factory=list)
    classes: list[ParsedClass] = Field(default_factory=list)
    module_docstring: str | None = None
    error: str | None = Field(
        default=None,
        description="Non-None when the file could not be fully parsed",
    )
