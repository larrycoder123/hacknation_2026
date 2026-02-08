from typing import Optional, Literal, List
from pydantic import BaseModel
from .knowledge import KnowledgeArticle

Priority = Literal["High", "Medium", "Low"]
TicketStatus = Literal["Open", "Pending", "Resolved", "Closed"]

class Ticket(BaseModel):
    """Represents a support ticket."""
    id: str
    customer_name: str
    subject: str
    priority: Priority
    status: TicketStatus
    time_ago: str
    avatar_url: Optional[str] = None
    last_message: Optional[str] = None

class CloseTicketPayload(BaseModel):
    """Payload for closing a ticket."""
    ticket_id: str
    resolution_type: Literal["Resolved Successfully", "Not Applicable"]
    notes: Optional[str] = None
    add_to_knowledge_base: bool

class CloseTicketResponse(BaseModel):
    """Response after closing a ticket."""
    status: str
    message: str
    knowledge_article: Optional[KnowledgeArticle] = None
