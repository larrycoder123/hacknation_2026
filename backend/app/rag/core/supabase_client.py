"""Supabase client for RAG component."""

from functools import lru_cache

from supabase import Client, create_client

from .config import settings


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client instance.

    Returns:
        Configured Supabase client
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
        )

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
