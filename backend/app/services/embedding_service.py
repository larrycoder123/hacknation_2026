"""Embedding generation via OpenAI SDK (text-embedding-3-large, 3072-dim)."""

from openai import OpenAI

from app.core.config import get_settings

_openai_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    """Get or create the OpenAI client singleton."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def generate_embedding(text: str) -> list[float]:
    """Generate a single embedding vector.

    Args:
        text: Text to embed.

    Returns:
        List of floats (3072-dim by default).
    """
    return generate_embeddings([text])[0]


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []

    settings = get_settings()
    client = _get_openai()
    response = client.embeddings.create(
        input=texts,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
    )
    return [item.embedding for item in response.data]
