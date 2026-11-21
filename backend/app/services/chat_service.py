"""Chat service – retrieve context and query the LLM."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.llm.client import LLMClient
    from app.retrieval.hybrid import HybridRetriever
    from app.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


class SourceReference(BaseModel):
    """A source citation attached to a chat answer."""

    entity_id: str = ""
    name: str = ""
    entity_type: str = ""
    file_path: str = ""
    line_start: int | None = None
    line_end: int | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    """Full response from the chat service."""

    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    retrieval_results: list[dict] = Field(default_factory=list)


class ChatService:
    """Orchestrates retrieval-augmented generation for code Q&A."""

    def __init__(
        self,
        retriever: HybridRetriever,
        llm_client: LLMClient,
    ) -> None:
        self.retriever = retriever
        self.llm_client = llm_client

    async def ask(
        self,
        repo_id: str,
        question: str,
        conversation_history: list[dict] | None = None,
    ) -> ChatResponse:
        """Answer a question about a repository.

        1. Retrieve relevant context via the hybrid retriever.
        2. Build a prompt using the retrieved evidence.
        3. Call the LLM.
        4. Return the answer together with source references.

        Parameters
        ----------
        repo_id:
            Repository to query.
        question:
            User's natural-language question.
        conversation_history:
            Prior messages in ``[{"role": ..., "content": ...}]`` format.

        Returns
        -------
        ChatResponse
        """
        # 1. Retrieve context
        from app.retrieval.models import RetrievalResult as _RR  # noqa: F811 – local alias

        try:
            results: list[_RR] = await self.retriever.search(
                repo_id=repo_id,
                query=question,
                limit=10,
            )
        except Exception:
            logger.exception("Retrieval failed for question in repo %s", repo_id)
            results = []

        # 2. Build prompt
        from app.llm.prompts import build_chat_prompt

        messages = build_chat_prompt(
            question=question,
            context_results=results,
            conversation_history=conversation_history,
        )

        # 3. Call LLM
        from app.core.errors import LLMError

        try:
            answer = await self.llm_client.generate(messages, stream=False)
            if not isinstance(answer, str):
                # Shouldn't happen with stream=False, but be defensive
                answer = "".join([chunk async for chunk in answer])
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(
                message="Failed to generate chat response",
                details={"error": str(exc)},
            ) from exc

        # 4. Build response
        sources = [
            SourceReference(
                entity_id=r.entity_id,
                name=r.name,
                entity_type=r.entity_type,
                file_path=r.file_path,
                line_start=r.line_start,
                line_end=r.line_end,
                score=r.score,
            )
            for r in results
        ]

        return ChatResponse(
            answer=answer,
            sources=sources,
            retrieval_results=[r.model_dump() for r in results],
        )
