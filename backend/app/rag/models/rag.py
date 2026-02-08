"""Pydantic models for SupportMind RAG agent."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.rag.core.llm import TokenUsage


class RagStatus(StrEnum):
    """Status of RAG query."""

    SUCCESS = "success"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"


class CorpusSourceType(StrEnum):
    """Source types in retrieval_corpus."""

    SCRIPT = "SCRIPT"
    KB = "KB"
    TICKET_RESOLUTION = "TICKET_RESOLUTION"


class RagInput(BaseModel):
    """Input for RAG query."""

    question: str = Field(..., description="User question")
    category: str | None = Field(default=None, description="Issue category filter")
    source_types: list[CorpusSourceType] | None = Field(
        default=None, description="Filter by source types"
    )
    top_k: int = Field(default=10, description="Number of evidence items to return")
    ticket_number: str | None = Field(
        default=None, description="Ticket number for retrieval logging"
    )
    conversation_id: str | None = Field(
        default=None, description="Conversation ID for pre-ticket retrieval logging"
    )


class QueryVariant(BaseModel):
    """A query variant for retrieval."""

    query: str = Field(..., description="Search query text")
    rationale: str = Field(..., description="Why this variant helps")


class RetrievalPlan(BaseModel):
    """Plan for retrieving relevant corpus entries."""

    queries: list[QueryVariant] = Field(
        ...,
        description="2-4 query variants to search",
        min_length=2,
        max_length=4,
    )


class CorpusHit(BaseModel):
    """A retrieved entry from retrieval_corpus."""

    source_type: str = Field(..., description="SCRIPT, KB, or TICKET_RESOLUTION")
    source_id: str = Field(..., description="Source identifier (Script_ID, KB_Article_ID, or Ticket_Number)")
    title: str = Field(default="", description="Entry title")
    content: str = Field(..., description="Entry content")
    category: str | None = Field(default="", description="Issue category")
    module: str | None = Field(default="", description="Module")
    tags: str | None = Field(default="", description="Tags")
    similarity: float = Field(..., description="Vector similarity score (0-1)")
    rerank_score: float | None = Field(default=None, description="Reranker relevance score")
    confidence: float = Field(default=0.5, description="Confidence score from corpus")
    usage_count: int = Field(default=0, description="How often this entry has been used")
    updated_at: str | None = Field(default=None, description="When this entry was last updated")


class SourceDetail(BaseModel):
    """Enriched metadata from connected tables."""

    source_type: str = Field(..., description="SCRIPT, KB, or TICKET_RESOLUTION")
    source_id: str = Field(..., description="Source identifier")
    title: str = Field(default="", description="Entry title")
    # KB enrichment
    lineage_ticket: str | None = Field(default=None, description="Linked ticket from KB_Lineage")
    lineage_conversation: str | None = Field(default=None, description="Linked conversation from KB_Lineage")
    lineage_script: str | None = Field(default=None, description="Linked script from KB_Lineage")
    # Script enrichment
    script_purpose: str | None = Field(default=None, description="Script purpose from Scripts_Master")
    script_inputs: str | None = Field(default=None, description="Required inputs from Scripts_Master")
    # Ticket enrichment
    ticket_subject: str | None = Field(default=None, description="Ticket subject")
    ticket_resolution: str | None = Field(default=None, description="Ticket resolution notes")
    ticket_root_cause: str | None = Field(default=None, description="Root cause")


class Citation(BaseModel):
    """A citation in the answer."""

    source_type: str = Field(..., description="SCRIPT, KB, or TICKET_RESOLUTION")
    source_id: str = Field(..., description="Source identifier")
    title: str = Field(default="", description="Source title")
    quote: str | None = Field(default=None, description="Relevant quote snippet")


class RagAnswer(BaseModel):
    """Structured answer from RAG LLM call."""

    answer: str = Field(..., description="The answer text")
    citations: list[Citation] = Field(
        default_factory=list, description="Supporting citations"
    )
    confidence: str = Field(
        default="medium", description="Confidence level: high, medium, low"
    )


class RagResult(BaseModel):
    """Complete result of RAG query."""

    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    citations: list[Citation] = Field(default_factory=list, description="Citations")
    status: RagStatus = Field(..., description="Query status")
    evidence_count: int = Field(default=0, description="Number of evidence items used")
    retrieval_queries: list[str] = Field(
        default_factory=list, description="Queries used for retrieval"
    )
    top_hits: list[CorpusHit] = Field(
        default_factory=list, description="Top evidence hits for caller inspection"
    )

    def to_context(self) -> str:
        """Format result for passing to another LLM as context."""
        citations_text = "\n".join(
            f"[{i + 1}] {c.source_type}: {c.title} ({c.source_id})"
            for i, c in enumerate(self.citations)
        )
        return f"{self.answer}\n\nSources:\n{citations_text}"


class RagState(BaseModel):
    """State for RAG LangGraph workflow."""

    # Input
    input: RagInput

    # Planning
    retrieval_plan: RetrievalPlan | None = None

    # Retrieval
    candidates: list[CorpusHit] = Field(default_factory=list)
    evidence: list[CorpusHit] = Field(default_factory=list)

    # Enrichment
    source_details: list[SourceDetail] = Field(default_factory=list)

    # Answer generation
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)

    # Validation
    validation_passed: bool = False
    attempt: int = 0
    top_k: int = 10

    # Result
    status: RagStatus = RagStatus.SUCCESS
    error: str | None = None

    # Extra context (gap detection)
    retrieval_log_summary: str | None = None

    # Token tracking
    tokens: TokenUsage = Field(default_factory=TokenUsage)

    model_config = ConfigDict(use_enum_values=True)
