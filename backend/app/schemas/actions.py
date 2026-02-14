"""Pydantic model for RAG-powered suggested actions."""

from typing import Literal, Optional
from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of how a suggestion's match score was computed."""

    vector_similarity: float
    rerank_score: float | None
    confidence: float
    usage_count: int
    freshness: float
    learning_score: float
    final_score: float


class AdaptedSuggestion(BaseModel):
    """Structured output from the suggestion adaptation LLM call."""
    adapted_summary: str
    draft_reply: str


class SuggestedAction(BaseModel):
    """A suggested action returned by the RAG pipeline for a support agent.

    Types: 'script' (runbook), 'response' (KB article), 'action' (ticket resolution).
    The adapted_summary is an LLM-generated plain-language version of the top hit.
    The draft_reply is a customer-facing message the agent can send directly.
    """

    id: str
    type: Literal['script', 'response', 'action']
    confidence_score: float
    title: str
    description: str
    content: str
    source: str
    adapted_summary: Optional[str] = None
    draft_reply: Optional[str] = None
    score_breakdown: Optional[ScoreBreakdown] = None
