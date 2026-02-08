"""Schemas module - Pydantic models for API request/response validation."""

from .actions import SuggestedAction
from .conversations import (
    CloseConversationPayload,
    CloseConversationResponse,
    Conversation,
    ConversationStatus,
    Priority,
)
from .learning import (
    ConfidenceUpdate,
    EventType,
    GapClassification,
    KBDraftFromGap,
    KBLineageRecord,
    LearningEventRecord,
    RetrievalLogEntry,
    ReviewDecision,
    SelfLearningResult,
)
from .messages import Message, Sender
from .tickets import Ticket, TicketCreateRequest

__all__ = [
    # Actions
    "SuggestedAction",
    # Conversations
    "Conversation",
    "CloseConversationPayload",
    "CloseConversationResponse",
    "ConversationStatus",
    "Priority",
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
    "TicketCreateRequest",
]
