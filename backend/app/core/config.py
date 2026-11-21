"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """RepoLens application settings.

    Values are loaded from environment variables and an optional `.env` file.
    """

    # ── Neo4j ────────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

    # ── LLM ──────────────────────────────────────────────────────────────
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "llama3"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: int = 60

    # ── Embeddings ───────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32

    # ── Backend server ───────────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8080
    LOG_LEVEL: str = "INFO"

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        """Accept a comma-separated string *or* an already-parsed list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Ingestion limits ─────────────────────────────────────────────────
    MAX_REPO_SIZE_MB: int = 500
    MAX_FILE_SIZE_KB: int = 512
    MAX_FILES: int = 10000

    # ── MCP server ───────────────────────────────────────────────────────
    MCP_SERVER_HOST: str = "0.0.0.0"
    MCP_SERVER_PORT: int = 8081

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
