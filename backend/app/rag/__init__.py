"""
SupportMind RAG Component

Provides retrieval-augmented generation for:
1. Question answering against the retrieval_corpus (scripts, KB articles, tickets)
2. Gap detection for the self-learning loop (classifies new vs existing knowledge)
"""

# Core providers
from app.rag.core import Embedder, LLM, Reranker, get_supabase_client, settings

# RAG models
from app.rag.models import (
    Citation,
    CorpusHit,
    CorpusSourceType,
    GapDetectionInput,
    GapDetectionResult,
    KnowledgeDecision,
    KnowledgeDecisionType,
    RagAnswer,
    RagInput,
    RagResult,
    RagState,
    RagStatus,
    RetrievalLogEntry,
    RetrievalOutcome,
    RetrievalPlan,
    SourceDetail,
)

# Pipelines
from app.rag.agent import (
    create_gap_detection_graph,
    create_rag_graph,
    run_gap_detection,
    run_rag,
)

__all__ = [
    # Core
    "settings",
    "Embedder",
    "LLM",
    "Reranker",
    "get_supabase_client",
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
    # Pipelines
    "create_rag_graph",
    "run_rag",
    "create_gap_detection_graph",
    "run_gap_detection",
]
