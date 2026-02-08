"""Schemas module - Pydantic models for API request/response validation."""

from .actions import SuggestedAction
from .knowledge import KnowledgeArticle, KnowledgeArticleCreateRequest
from .messages import Message, TicketConversation, Sender
from .tickets import (
    Ticket,
    CloseTicketPayload,
    CloseTicketResponse,
    Priority,
    TicketStatus,
)

__all__ = [
    # Actions
    "SuggestedAction",
    # Knowledge
    "KnowledgeArticle",
    "KnowledgeArticleCreateRequest",
    # Messages
    "Message",
    "TicketConversation",
    "Sender",
    # Tickets
    "Ticket",
    "CloseTicketPayload",
    "CloseTicketResponse",
    "Priority",
    "TicketStatus",
]
