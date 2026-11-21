"""LLM module – OpenAI-compatible client and prompt templates."""

from app.llm.client import LLMClient
from app.llm.prompts import (
    build_architecture_prompt,
    build_chat_prompt,
    build_impact_summary_prompt,
)

__all__ = [
    "LLMClient",
    "build_architecture_prompt",
    "build_chat_prompt",
    "build_impact_summary_prompt",
]
