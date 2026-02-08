from typing import Literal
from pydantic import BaseModel

Sender = Literal["agent", "customer", "system"]


class Message(BaseModel):
    """Represents a single message in a ticket conversation."""
    id: str
    ticket_id: str
    sender: Sender
    content: str
    timestamp: str
