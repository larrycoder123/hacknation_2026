"""Pydantic model for conversation messages."""

from typing import Literal
from pydantic import BaseModel

Sender = Literal["agent", "customer", "system"]


class Message(BaseModel):
    """A single message in a conversation (agent, customer, or system)."""
    id: str
    conversation_id: str
    sender: Sender
    content: str
    timestamp: str
