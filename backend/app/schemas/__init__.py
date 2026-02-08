"""Schemas module - Pydantic models for API request/response validation."""

from .actions import SuggestedAction
from .knowledge import KnowledgeArticle, KnowledgeArticleCreateRequest
from .learning import (
    ConfidenceUpdate,
    KBDraftFromGap,
    KBLineageRecord,
    LearningEventRecord,
    RetrievalLogEntry,
    ReviewDecision,
    SelfLearningResult,
)
from .messages import Message, Sender
from .tickets import (
    CloseTicketPayload,
    CloseTicketResponse,
    Priority,
    Ticket,
    TicketStatus,
)

__all__ = [
    # Actions
    "SuggestedAction",
    # Knowledge
    "KnowledgeArticle",
    "KnowledgeArticleCreateRequest",
    # Learning
    "ConfidenceUpdate",
    "KBDraftFromGap",
    "KBLineageRecord",
    "LearningEventRecord",
    "RetrievalLogEntry",
    "ReviewDecision",
    "SelfLearningResult",
    # Messages
    "Message",
    "Sender",
    # Tickets
    "Ticket",
    "CloseTicketPayload",
    "CloseTicketResponse",
    "Priority",
    "TicketStatus",
]
