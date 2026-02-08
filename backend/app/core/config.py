"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# .env lives at the project root (one level above backend/)
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "SupportMind Backend"
    debug: bool = False

    # LLM configuration
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # Embedding
    embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 3072

    # Self-learning thresholds
    gap_similarity_threshold: float = 0.75
    confidence_delta_resolved: float = 0.10
    confidence_delta_partial: float = 0.02
    confidence_delta_unhelpful: float = -0.05

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
