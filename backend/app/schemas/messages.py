from typing import Literal, List
from pydantic import BaseModel

Sender = Literal["agent", "customer", "system"]

class Message(BaseModel):
    """Represents a single message in a ticket conversation."""
    id: str
    ticket_id: str
    sender: Sender
    content: str
    timestamp: str

class TicketConversation(BaseModel):
    """Complete conversation data for a ticket."""
    ticket_id: str
    messages: List[Message]
