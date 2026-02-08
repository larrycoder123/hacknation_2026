"""Supabase client singleton."""

import threading

from supabase import Client, create_client

from app.core.config import get_settings

_supabase_instance: Client | None = None
_lock = threading.Lock()


def get_supabase() -> Client:
    """Get or create the Supabase client singleton (thread-safe)."""
    global _supabase_instance
    if _supabase_instance is None:
        with _lock:
            if _supabase_instance is None:
                settings = get_settings()
                _supabase_instance = create_client(
                    settings.supabase_url,
                    settings.supabase_service_role_key,
                )
    return _supabase_instance
