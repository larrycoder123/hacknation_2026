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


class SimulateCustomerMessage(BaseModel):
    """A simplified message for the customer simulation endpoint."""
    sender: Literal["agent", "customer"]
    content: str


class SimulateCustomerRequest(BaseModel):
    """Request body for POST /conversations/{id}/simulate-customer."""
    messages: list[SimulateCustomerMessage]


class SuggestedActionsRequest(BaseModel):
    """Request body for POST /conversations/{id}/suggested-actions."""
    messages: list[SimulateCustomerMessage] = []
    exclude_ids: list[str] = []


class SimulateCustomerResponse(BaseModel):
    """LLM-generated customer reply."""
    content: str
    resolved: bool
