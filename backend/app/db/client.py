"""Supabase client singleton."""

from supabase import Client, create_client

from app.core.config import get_settings

_supabase_instance: Client | None = None


def get_supabase() -> Client:
    """Get or create the Supabase client singleton."""
    global _supabase_instance
    if _supabase_instance is None:
        settings = get_settings()
        _supabase_instance = create_client(
            settings.supabase_url,
            settings.supabase_key,
        )
    return _supabase_instance
