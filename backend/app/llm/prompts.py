"""Prompt templates for LLM interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.retrieval.models import RetrievalResult

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_CHAT_SYSTEM_PROMPT = """\
You are RepoLens, an expert code-analysis assistant.
You answer questions about a code repository using ONLY the retrieved code \
evidence provided below.

Rules:
1. Base every claim on the retrieved code. Cite file paths and line numbers.
2. If the evidence is insufficient to answer the question, say so explicitly \
   rather than guessing.
3. Never invent code, functions, or APIs that are not present in the evidence.
4. Keep answers concise and well-structured. Use markdown for formatting.
5. When referencing code, use fenced code blocks with the language identifier.
"""

_IMPACT_SYSTEM_PROMPT = """\
You are RepoLens, a code-impact analysis assistant.
Summarise the impact of modifying the specified entity based on the \
dependency data provided. Focus on:
1. What would break if this entity's signature or behaviour changed.
2. Which files and modules are affected directly and transitively.
3. Risk assessment (low / medium / high) with justification.
Keep the summary concise and actionable.
"""

_ARCHITECTURE_SYSTEM_PROMPT = """\
You are RepoLens, a software-architecture analyst.
Given repository statistics and key entities, produce a concise architectural \
overview covering:
1. High-level structure and module organisation.
2. Key abstractions and design patterns visible in the entity list.
3. Potential areas of concern (e.g. high coupling, large files).
Use markdown with headers and bullet points.
"""


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_chat_prompt(
    question: str,
    context_results: list[RetrievalResult],
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    """Build a chat-completion messages list for a code Q&A turn.

    Parameters
    ----------
    question:
        The user's current question.
    context_results:
        Retrieved code entities to use as evidence.
    conversation_history:
        Previous messages in the conversation (``[{"role": ..., "content": ...}]``).

    Returns
    -------
    list[dict]
        OpenAI-style messages list ready for the LLM client.
    """
    context_block = _format_context(context_results)

    messages: list[dict] = [
        {"role": "system", "content": _CHAT_SYSTEM_PROMPT},
    ]

    if conversation_history:
        messages.extend(conversation_history)

    user_content = (
        f"### Retrieved Code Context\n\n{context_block}\n\n"
        f"### Question\n\n{question}"
    )
    messages.append({"role": "user", "content": user_content})
    return messages


def build_impact_summary_prompt(
    entity_name: str,
    impact_data: dict,
) -> list[dict]:
    """Build messages for an impact-analysis summary.

    Parameters
    ----------
    entity_name:
        Name of the entity being analysed.
    impact_data:
        Dictionary with keys like ``direct_dependents``, ``indirect_dependents``,
        ``affected_files``, ``dependency_paths``, ``total_impact_count``.

    Returns
    -------
    list[dict]
    """
    details_parts: list[str] = [
        f"**Entity:** {entity_name}",
        f"**Direct dependents:** {len(impact_data.get('direct_dependents', []))}",
        f"**Indirect dependents:** {len(impact_data.get('indirect_dependents', []))}",
        f"**Affected files:** {len(impact_data.get('affected_files', []))}",
        f"**Total impact count:** {impact_data.get('total_impact_count', 0)}",
    ]

    dep_paths = impact_data.get("dependency_paths", [])
    if dep_paths:
        details_parts.append("\n**Sample dependency paths:**")
        for path in dep_paths[:10]:
            details_parts.append(f"- {' → '.join(path)}")

    direct = impact_data.get("direct_dependents", [])
    if direct:
        details_parts.append("\n**Direct dependents:**")
        for dep in direct[:20]:
            if isinstance(dep, dict):
                details_parts.append(f"- {dep.get('name', dep.get('entity_id', str(dep)))}")
            else:
                details_parts.append(f"- {dep}")

    return [
        {"role": "system", "content": _IMPACT_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(details_parts)},
    ]


def build_architecture_prompt(
    repo_stats: dict,
    top_entities: list[dict],
) -> list[dict]:
    """Build messages for an architecture-overview request.

    Parameters
    ----------
    repo_stats:
        Dictionary with keys like ``total_files``, ``total_functions``,
        ``total_classes``, ``languages``, etc.
    top_entities:
        List of dicts describing the most important entities (name, type, file,
        connections, etc.).

    Returns
    -------
    list[dict]
    """
    stats_lines: list[str] = ["### Repository Statistics"]
    for key, value in repo_stats.items():
        stats_lines.append(f"- **{key}:** {value}")

    entity_lines: list[str] = ["\n### Key Entities"]
    for entity in top_entities[:30]:
        name = entity.get("name", "unknown")
        etype = entity.get("entity_type", "")
        fpath = entity.get("file_path", "")
        entity_lines.append(f"- [{etype}] **{name}** in `{fpath}`")

    return [
        {"role": "system", "content": _ARCHITECTURE_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(stats_lines + entity_lines)},
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_context(results: list[RetrievalResult]) -> str:
    """Format retrieval results into a readable context block."""
    if not results:
        return "_No relevant code found._"

    parts: list[str] = []
    for i, result in enumerate(results, 1):
        header = f"**[{i}] {result.entity_type}: {result.name}**"
        location = f"`{result.file_path}`"
        if result.line_start is not None:
            location += f" (lines {result.line_start}"
            if result.line_end is not None:
                location += f"–{result.line_end}"
            location += ")"

        block = [header, location]
        if result.source:
            block.append(f"```python\n{result.source}\n```")
        if result.graph_context:
            block.append(f"_Graph context: {result.graph_context}_")
        parts.append("\n".join(block))

    return "\n\n---\n\n".join(parts)
