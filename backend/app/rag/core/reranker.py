"""Reranker provider for RAG component."""

from dataclasses import dataclass

import cohere

from .config import settings


@dataclass
class RankedDocument:
    """A document with reranking score."""

    index: int
    text: str
    relevance_score: float


class Reranker:
    """Cohere reranking wrapper."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.cohere_api_key
        self.model = model or settings.cohere_rerank_model
        self._client: cohere.Client | None = None

    @property
    def client(self) -> cohere.Client:
        """Lazy-load Cohere client."""
        if self._client is None:
            self._client = cohere.Client(api_key=self.api_key)
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if reranking is available (API key configured)."""
        return bool(self.api_key)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[RankedDocument]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Number of top results to return (None = all)

        Returns:
            List of RankedDocument sorted by relevance
        """
        if not documents:
            return []

        if not self.is_available:
            # Fallback: return documents in original order with dummy scores
            return [
                RankedDocument(index=i, text=doc, relevance_score=1.0 - i * 0.01)
                for i, doc in enumerate(documents[:top_k] if top_k else documents)
            ]

        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=documents,
            top_n=top_k or len(documents),
            return_documents=True,
        )

        return [
            RankedDocument(
                index=result.index,
                text=result.document.text,
                relevance_score=result.relevance_score,
            )
            for result in response.results
        ]
