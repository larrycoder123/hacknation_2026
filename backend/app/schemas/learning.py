"""Pydantic models for the self-learning pipeline."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Event type classification ────────────────────────────────────────

EventType = Literal["GAP", "CONTRADICTION", "CONFIRMED"]
GapClassification = Literal["SAME_KNOWLEDGE", "CONTRADICTS", "NEW_KNOWLEDGE"]

# ── Retrieval log (read from DB) ──────────────────────────────────────


class RetrievalLogEntry(BaseModel):
    """A single RAG search attempt stored in retrieval_log."""

    retrieval_id: str
    ticket_number: str | None = None
    conversation_id: str | None = None
    attempt_number: int = 1
    query_text: str = ""
    source_type: str | None = None
    source_id: str | None = None
    similarity_score: float | None = None
    outcome: Literal["RESOLVED", "UNHELPFUL", "PARTIAL"] | None = None
    created_at: datetime | None = None


# ── Confidence update result ──────────────────────────────────────────


class ConfidenceUpdate(BaseModel):
    """Result of updating a single retrieval_corpus row's confidence."""

    source_type: str
    source_id: str
    delta: float
    new_confidence: float
    new_usage_count: int


# ── KB draft from gap detection (LLM output schema) ──────────────────


class KBDraftFromGap(BaseModel):
    """Structured output the LLM returns when drafting a KB article from a gap."""

    title: str = Field(description="Concise, searchable KB article title")
    body: str = Field(description="Full article body with problem description and solution")
    tags: str = Field(description="Comma-separated tags for searchability")
    category: str | None = Field(
        default=None,
        description="Issue category (must match an existing category name)",
    )
    module: str | None = Field(default=None, description="Product module if applicable")


# ── KB lineage record ─────────────────────────────────────────────────


class KBLineageRecord(BaseModel):
    """One provenance link from a KB article to its source."""

    kb_article_id: str
    source_type: Literal["Ticket", "Conversation", "Script"]
    source_id: str
    relationship: Literal["CREATED_FROM", "REFERENCES"]
    evidence_snippet: str | None = None
    event_timestamp: datetime | None = None


# ── Learning event ────────────────────────────────────────────────────


class LearningEventRecord(BaseModel):
    """A row in the learning_events audit table."""

    event_id: str
    trigger_ticket_number: str
    detected_gap: str
    event_type: EventType = "GAP"
    proposed_kb_article_id: str | None = None
    flagged_kb_article_id: str | None = None
    draft_summary: str
    final_status: Literal["Approved", "Rejected"] | None = None
    reviewer_role: str | None = None
    event_timestamp: datetime | None = None


# ── Review request ────────────────────────────────────────────────────


class ReviewDecision(BaseModel):
    """Payload for POST /learning-events/{id}/review."""

    decision: Literal["Approved", "Rejected"]
    reviewer_role: Literal["Tier 3 Support", "Support Ops Review"] = "Tier 3 Support"
    reason: str | None = None


# ── KB article summary (for review UI) ───────────────────────────────


class KBArticleSummary(BaseModel):
    """Subset of knowledge_articles for display in the review UI."""

    kb_article_id: str
    title: str
    body: str
    tags: str | None = None
    module: str | None = None
    category: str | None = None
    status: str | None = None


# ── Learning event detail (with joined data) ─────────────────────────


class LearningEventDetail(BaseModel):
    """Learning event with joined KB article and ticket data for the review page."""

    event_id: str
    trigger_ticket_number: str
    detected_gap: str
    event_type: EventType = "GAP"
    proposed_kb_article_id: str | None = None
    flagged_kb_article_id: str | None = None
    draft_summary: str
    final_status: Literal["Approved", "Rejected"] | None = None
    reviewer_role: str | None = None
    event_timestamp: datetime | None = None
    proposed_article: KBArticleSummary | None = None
    flagged_article: KBArticleSummary | None = None
    trigger_ticket_subject: str | None = None
    trigger_ticket_description: str | None = None
    trigger_ticket_resolution: str | None = None


class LearningEventListResponse(BaseModel):
    """Paginated list of learning events."""

    events: list[LearningEventDetail]
    total_count: int


# ── Aggregate result ──────────────────────────────────────────────────


class SelfLearningResult(BaseModel):
    """Response from POST /tickets/{id}/learn."""

    ticket_number: str
    retrieval_logs_processed: int
    confidence_updates: list[ConfidenceUpdate]
    gap_classification: GapClassification | None = None
    matched_kb_article_id: str | None = None
    match_similarity: float | None = None
    learning_event_id: str | None = None
    drafted_kb_article_id: str | None = None
