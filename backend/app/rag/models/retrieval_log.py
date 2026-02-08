"""Models for retrieval logging to Supabase."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RetrievalOutcome(StrEnum):
    """Outcome of a retrieval attempt."""

    RESOLVED = "RESOLVED"
    UNHELPFUL = "UNHELPFUL"
    PARTIAL = "PARTIAL"


class RetrievalLogEntry(BaseModel):
    """A single retrieval attempt logged to the retrieval_log table."""

    retrieval_id: str = Field(..., description="Primary key (e.g. RET-{uuid})")
    ticket_number: str | None = Field(
        default=None, description="Linked ticket for grouping attempts"
    )
    attempt_number: int = Field(default=1, description="Attempt number within ticket")
    query_text: str = Field(default="", description="What the agent searched for")
    source_type: str = Field(default="", description="SCRIPT / KB / TICKET_RESOLUTION")
    source_id: str = Field(default="", description="Which corpus row was returned")
    similarity_score: float = Field(default=0.0, description="Vector similarity")
    outcome: RetrievalOutcome = Field(
        default=RetrievalOutcome.PARTIAL, description="Retrieval outcome"
    )
    created_at: datetime | None = Field(
        default=None, description="Timestamp of retrieval"
    )
