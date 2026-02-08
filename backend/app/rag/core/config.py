"""Configuration management for RAG component."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """RAG component settings loaded from environment variables."""

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-large"
    openai_chat_model: str = "gpt-4o"
    embedding_dimension: int = 3072

    # Cohere (optional, for reranking)
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-english-v3.0"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Retrieval settings
    default_top_k: int = 10
    max_retrieval_candidates: int = 40

    # Gap detection threshold
    gap_similarity_threshold: float = 0.75

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
