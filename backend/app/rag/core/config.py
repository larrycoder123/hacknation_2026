"""Configuration management for RAG component."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# .env lives at the project root (one level above backend/)
_ENV_FILE = str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    """RAG component settings loaded from environment variables."""

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-large"
    openai_chat_model: str = "gpt-5.2"
    embedding_dimension: int = 3072

    # Cohere (optional, for reranking)
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-v4.0-pro"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Retrieval settings
    default_top_k: int = 10
    max_retrieval_candidates: int = 40

    # Learning-adjusted ranking (post-rerank blending)
    # final_score = rerank_score * (1 - blend_weight + blend_weight * learning_score)
    # learning_score = confidence_weight * confidence
    #               + usage_weight * usage_factor
    #               + freshness_weight * freshness
    confidence_blend_weight: float = 0.3
    confidence_signal_weight: float = 0.6
    usage_signal_weight: float = 0.3
    freshness_signal_weight: float = 0.1
    freshness_half_life_days: int = 365

    # Gap detection threshold
    gap_similarity_threshold: float = 0.75

    model_config = {"env_file": _ENV_FILE, "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
