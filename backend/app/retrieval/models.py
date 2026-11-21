"""Data models for retrieval results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    """A single result returned by any retriever."""

    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: str = Field(..., description="Entity type: function, class, module, file")
    name: str = Field(..., description="Short name of the entity")
    qualified_name: str = Field("", description="Fully-qualified name")
    file_path: str = Field("", description="Source file path relative to the repo")
    line_start: int | None = Field(None, description="Start line in source file")
    line_end: int | None = Field(None, description="End line in source file")
    source: str = Field("", description="Source code snippet")
    score: float | None = Field(None, description="Relevance score (0-1)")
    retrieval_method: str = Field("", description="Method used: semantic, graph, hybrid")
    graph_context: str | None = Field(
        None, description="Additional context from graph traversal"
    )
    reason: str = Field("", description="Human-readable explanation of why this result matched")
