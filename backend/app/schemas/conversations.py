from typing import Optional, Literal
from pydantic import BaseModel, Field
from .tickets import Priority, Ticket
from .learning import SelfLearningResult

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
    conversation_id: str = Field(min_length=1, max_length=50)
    resolution_type: Literal["Resolved Successfully", "Not Applicable"]
    notes: Optional[str] = Field(default=None, max_length=5000)
    create_ticket: bool

class CloseConversationResponse(BaseModel):
    """Response after closing a conversation."""
    status: str
    message: str
    ticket: Optional[Ticket] = None
    learning_result: Optional[SelfLearningResult] = None
    warnings: list[str] = []
