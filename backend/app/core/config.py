"""Core configuration module for RepoLens."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "repolens_dev_password"
    neo4j_database: str = "neo4j"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "meta-llama/Llama-3.1-8B-Instruct"


settings = Settings()
