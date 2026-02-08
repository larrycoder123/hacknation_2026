from typing import List, Optional
from pydantic import BaseModel

class Ticket(BaseModel):
    """
    A ticket (Salesforce-style case record) generated from a resolved conversation.

    This schema represents the structured output from the LLM
    when summarizing a conversation into a reusable case record.
    """
    subject: str
    description: str
    resolution: str
    tags: List[str]
    category: Optional[str] = None
    related_error_codes: Optional[List[str]] = None
    steps_to_reproduce: Optional[str] = None
    resolution_steps: Optional[List[str]] = None
    customer_communication_template: Optional[str] = None
    internal_notes: Optional[str] = None

class TicketCreateRequest(BaseModel):
    """Request payload for creating a ticket from a conversation."""
    conversation_id: str
    resolution_notes: Optional[str] = None
    custom_tags: Optional[List[str]] = None
