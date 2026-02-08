"""Pydantic model for RAG-powered suggested actions."""

from typing import Literal, Optional
from pydantic import BaseModel


class SuggestedAction(BaseModel):
    """A suggested action returned by the RAG pipeline for a support agent.

    Types: 'script' (runbook), 'response' (KB article), 'action' (ticket resolution).
    The adapted_summary is an LLM-generated plain-language version of the top hit.
    """

    id: str
    type: Literal['script', 'response', 'action']
    confidence_score: float
    title: str
    description: str
    content: str
    source: str
    adapted_summary: Optional[str] = None
