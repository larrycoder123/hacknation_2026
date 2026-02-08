"""Models for gap detection in the self-learning loop."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.rag.models.rag import CorpusHit, SourceDetail


class KnowledgeDecisionType(StrEnum):
    """Classification of knowledge relative to existing corpus."""

    SAME_KNOWLEDGE = "SAME_KNOWLEDGE"
    CONTRADICTS = "CONTRADICTS"
    NEW_KNOWLEDGE = "NEW_KNOWLEDGE"


class KnowledgeDecision(BaseModel):
    """LLM classification of whether a ticket represents new or existing knowledge."""

    decision: KnowledgeDecisionType = Field(..., description="Classification result")
    reasoning: str = Field(..., description="Why this classification was chosen")
    best_match_source_id: str | None = Field(
        default=None, description="Closest matching corpus entry ID"
    )
    similarity_score: float = Field(
        default=0.0, description="Best similarity score found"
    )


class GapDetectionInput(BaseModel):
    """Input for gap detection — assembled from a resolved ticket + conversation."""

    ticket_number: str = Field(..., description="Ticket ID (e.g. CS-38908386)")
    conversation_id: str = Field(default="", description="Conversation ID")
    category: str = Field(default="", description="Issue category")
    subject: str = Field(default="", description="Ticket subject line")
    description: str = Field(default="", description="Ticket description")
    resolution: str = Field(default="", description="Resolution notes")
    root_cause: str = Field(default="", description="Root cause")
    transcript: str = Field(default="", description="Conversation transcript")
    script_id: str = Field(default="", description="Script ID used in resolution")
    retrieval_log_summary: str | None = Field(
        default=None,
        description="Summary of what happened during live support (e.g. '3 attempts: 1 RESOLVED, 1 PARTIAL, 1 UNHELPFUL')",
    )


class GapDetectionResult(BaseModel):
    """Result of gap detection — determines if ticket has new knowledge."""

    decision: KnowledgeDecision = Field(..., description="Classification result")
    retrieved_entries: list[CorpusHit] = Field(
        default_factory=list, description="Corpus entries found during search"
    )
    enriched_sources: list[SourceDetail] = Field(
        default_factory=list, description="Enriched metadata for retrieved entries"
    )
    query_used: str = Field(default="", description="Query constructed for search")
