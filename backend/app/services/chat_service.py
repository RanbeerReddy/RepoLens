"""Codebase Chat Service orchestrating Hybrid Retrieval and LLM Reasoning."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.graph.neo4j_client import Neo4jClient
from app.llm.prompts import build_chat_prompt
from app.llm.vllm_client import LLMError, VLLMClient
from app.retrieval.hybrid_search import HybridSearchEngine


class ChatSource(BaseModel):
    """Verified source citation grounded in retrieved code."""

    file_path: str
    start_line: int
    end_line: int
    qualified_name: str
    relevance_score: float
    citation: str = Field(description="Formatted reference like 'app/auth.py:20-42'")


class ChatResponse(BaseModel):
    """Structured response from the Codebase Chat Service."""

    query: str
    answer: str
    sources: list[ChatSource]
    retrieved_count: int
    llm_used: bool


class ChatService:
    """End-to-end RAG service answering codebase questions using verified evidence."""

    def __init__(
        self,
        retrieval_engine: Optional[HybridSearchEngine] = None,
        llm_client: Optional[VLLMClient] = None,
        neo4j_client: Optional[Neo4jClient] = None,
    ) -> None:
        self.retrieval_engine = retrieval_engine or HybridSearchEngine(client=neo4j_client)
        self.llm_client = llm_client or VLLMClient()

    def ask(
        self,
        query: str,
        repo_id: Optional[str] = None,
        top_k: int = 5,
    ) -> ChatResponse:
        """
        Executes hybrid retrieval, compiles verified context, and invokes LLM.
        Gracefully returns retrieved evidence if LLM is offline or unreachable.
        """
        # 1. Retrieve hybrid context
        results = self.retrieval_engine.search(query=query, limit=top_k, repo_id=repo_id)

        # 2. Extract verified sources
        sources = [
            ChatSource(
                file_path=r.file_path,
                start_line=r.start_line,
                end_line=r.end_line,
                qualified_name=r.qualified_name,
                relevance_score=r.final_score,
                citation=f"{r.file_path}:{r.start_line}-{r.end_line}",
            )
            for r in results
        ]

        if not results:
            return ChatResponse(
                query=query,
                answer="No relevant code was found in the repository for your query.",
                sources=[],
                retrieved_count=0,
                llm_used=False,
            )

        # 3. Format grounded prompt
        context_str = HybridSearchEngine.format_context_for_llm(results)
        prompt = build_chat_prompt(query=query, code_context=context_str)

        # 4. Generate grounded answer with vLLM
        try:
            answer = self.llm_client.generate(prompt)
            llm_used = True
        except LLMError as err:
            # Graceful degradation: present retrieved evidence without failing
            snippets = "\n".join(
                f"- **{s.qualified_name}** in `{s.citation}` (Score: {s.relevance_score:.2f})"
                for s in sources
            )
            answer = (
                f"*(Note: LLM inference server is currently offline. Retrieved code evidence:)*\n\n"
                f"{snippets}\n\n"
                f"**Retrieval diagnostic**: {err}"
            )
            llm_used = False

        return ChatResponse(
            query=query,
            answer=answer,
            sources=sources,
            retrieved_count=len(sources),
            llm_used=llm_used,
        )
