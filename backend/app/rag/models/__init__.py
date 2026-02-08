"""Pydantic models for SupportMind RAG component."""

from .corpus import (
    GapDetectionInput,
    GapDetectionResult,
    KnowledgeDecision,
    KnowledgeDecisionType,
)
from .rag import (
    Citation,
    CorpusHit,
    CorpusSourceType,
    RagAnswer,
    RagInput,
    RagResult,
    RagState,
    RagStatus,
    RetrievalPlan,
    SourceDetail,
)
from .retrieval_log import RetrievalLogEntry, RetrievalOutcome

__all__ = [
    # RAG models
    "CorpusSourceType",
    "RagInput",
    "RetrievalPlan",
    "CorpusHit",
    "SourceDetail",
    "Citation",
    "RagAnswer",
    "RagResult",
    "RagState",
    "RagStatus",
    # Gap detection models
    "KnowledgeDecisionType",
    "KnowledgeDecision",
    "GapDetectionInput",
    "GapDetectionResult",
    # Retrieval log
    "RetrievalLogEntry",
    "RetrievalOutcome",
]
