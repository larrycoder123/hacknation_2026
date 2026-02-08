from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, Field, StringConstraints

Tag = Annotated[str, StringConstraints(max_length=100)]
ErrorCode = Annotated[str, StringConstraints(max_length=50)]
ResolutionStep = Annotated[str, StringConstraints(max_length=2000)]

TicketStatus = Literal["Open", "Closed", "Pending"]
CaseType = Literal["Incident", "Service Request", "Problem"]
Priority = Literal["High", "Medium", "Low"]


class Ticket(BaseModel):
    """
    A ticket (Salesforce-style case record) generated from a resolved conversation.

    This schema represents the structured output from the LLM
    when summarizing a conversation into a reusable case record.
    """
    ticket_number: Optional[str] = None
    subject: str = Field(max_length=500)
    description: str = Field(max_length=10000)
    resolution: str = Field(max_length=10000)
    tags: List[Tag] = Field(max_length=50)
    category: Optional[str] = Field(default=None, max_length=200)
    related_error_codes: Optional[List[ErrorCode]] = Field(default=None, max_length=20)
    steps_to_reproduce: Optional[str] = Field(default=None, max_length=5000)
    resolution_steps: Optional[List[ResolutionStep]] = Field(default=None, max_length=30)
    customer_communication_template: Optional[str] = Field(default=None, max_length=5000)
    internal_notes: Optional[str] = Field(default=None, max_length=5000)


class TicketDBRow(BaseModel):
    """Flat representation of a ticket row for DB insertion."""
    ticket_number: str = Field(pattern=r"^CS-[A-F0-9]{8}$")
    created_at: str
    closed_at: str
    status: TicketStatus
    priority: Priority
    subject: str = Field(max_length=500)
    description: str = Field(max_length=10000)
    resolution: str = Field(max_length=10000)
    tags: str = Field(max_length=6000)
    case_type: CaseType


class TicketCreateRequest(BaseModel):
    """Request payload for creating a ticket from a conversation."""
    conversation_id: str
    resolution_notes: Optional[str] = None
    custom_tags: Optional[List[str]] = None
