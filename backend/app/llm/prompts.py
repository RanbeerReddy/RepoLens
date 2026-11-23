"""System prompts and prompt formatting for grounded codebase reasoning."""

from __future__ import annotations

SYSTEM_PROMPT = """You are RepoLens, an expert AI software architecture assistant.
Your task is to answer developer questions about a codebase using ONLY the provided code context.

RULES:
1. Ground your answer strictly in the provided code sources. Do NOT guess dependencies.
2. Every claim about where code lives or what calls what MUST include an inline citation:
   Format: [file_path:start_line-end_line].
3. If the provided context lacks enough evidence, state clearly what is missing.
4. Keep explanations concise, technical, and directly focused on the developer's question."""


def build_chat_prompt(query: str, code_context: str) -> str:
    """Builds a complete user prompt containing query and verified code evidence."""
    return f"""USER QUESTION:
{query}

RETRIEVED CODE CONTEXT:
{code_context}

Please provide a clear, grounded explanation citing file paths and line ranges."""
