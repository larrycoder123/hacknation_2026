"""Application configuration using Pydantic Settings."""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Environment variables can be set directly or via a .env file.
    """
    # Application
    app_name: str = "SupportMind Backend"
    debug: bool = False
    
    # OpenAI-compatible API configuration
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance to avoid re-reading env on every call."""
    return Settings()
