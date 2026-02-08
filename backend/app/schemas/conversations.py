from typing import Optional, Literal
from pydantic import BaseModel
from .tickets import Ticket

Priority = Literal["High", "Medium", "Low"]
ConversationStatus = Literal["Open", "Pending", "Resolved", "Closed"]

class Conversation(BaseModel):
    """Represents a support conversation (call/chat transcript)."""
    id: str
    customer_name: str
    subject: str
    priority: Priority
    status: ConversationStatus
    time_ago: str
    avatar_url: Optional[str] = None
    last_message: Optional[str] = None

class CloseConversationPayload(BaseModel):
    """Payload for closing a conversation."""
    conversation_id: str
    resolution_type: Literal["Resolved Successfully", "Not Applicable"]
    notes: Optional[str] = None
    create_ticket: bool

class CloseConversationResponse(BaseModel):
    """Response after closing a conversation."""
    status: str
    message: str
    ticket: Optional[Ticket] = None
