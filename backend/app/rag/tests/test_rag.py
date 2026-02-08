"""Tests for SupportMind RAG models."""

import pytest

from app.rag.models.rag import (
    Citation,
    CorpusHit,
    CorpusSourceType,
    QueryVariant,
    RagAnswer,
    RagInput,
    RagResult,
    RagState,
    RagStatus,
    RetrievalPlan,
    SourceDetail,
)
from app.rag.models.corpus import (
    GapDetectionInput,
    GapDetectionResult,
    KnowledgeDecision,
    KnowledgeDecisionType,
)
from app.rag.models.retrieval_log import RetrievalLogEntry, RetrievalOutcome


class TestCorpusSourceType:
    """Test CorpusSourceType enum."""

    def test_valid_values(self):
        assert CorpusSourceType.SCRIPT == "SCRIPT"
        assert CorpusSourceType.KB == "KB"
        assert CorpusSourceType.TICKET_RESOLUTION == "TICKET_RESOLUTION"


class TestRagInput:
    """Test RAG input validation."""

    def test_minimal_input(self):
        input_data = RagInput(question="How do I advance the property date?")
        assert input_data.question == "How do I advance the property date?"
        assert input_data.category is None
        assert input_data.source_types is None
        assert input_data.top_k == 10
        assert input_data.ticket_number is None

    def test_full_input(self):
        input_data = RagInput(
            question="How do I advance the property date?",
            category="Advance Property Date",
            source_types=[CorpusSourceType.SCRIPT, CorpusSourceType.KB],
            top_k=5,
            ticket_number="CS-38908386",
        )
        assert input_data.category == "Advance Property Date"
        assert len(input_data.source_types) == 2
        assert input_data.top_k == 5
        assert input_data.ticket_number == "CS-38908386"


class TestRetrievalPlan:
    """Test retrieval plan models."""

    def test_query_variant(self):
        variant = QueryVariant(
            query="advance property date backend fix",
            rationale="Search for date advance resolution scripts",
        )
        assert "advance" in variant.query
        assert variant.rationale

    def test_retrieval_plan(self):
        plan = RetrievalPlan(
            queries=[
                QueryVariant(query="Query 1", rationale="Rationale 1"),
                QueryVariant(query="Query 2", rationale="Rationale 2"),
            ]
        )
        assert len(plan.queries) == 2

    def test_plan_min_queries(self):
        with pytest.raises(ValueError):
            RetrievalPlan(
                queries=[QueryVariant(query="Only one", rationale="Not enough")]
            )


class TestCorpusHit:
    """Test corpus hit models."""

    def test_minimal_hit(self):
        hit = CorpusHit(
            source_type="SCRIPT",
            source_id="SCRIPT-0293",
            content="use <DATABASE>\ngo\nupdate ...",
            similarity=0.85,
        )
        assert hit.source_type == "SCRIPT"
        assert hit.source_id == "SCRIPT-0293"
        assert hit.similarity == 0.85
        assert hit.rerank_score is None
        assert hit.confidence == 0.0
        assert hit.usage_count == 0

    def test_full_hit(self):
        hit = CorpusHit(
            source_type="KB",
            source_id="KB-SYN-0001",
            title="Advance Property Date Fix",
            content="Steps to resolve...",
            category="Advance Property Date",
            module="Accounting / Date Advance",
            tags="date-advance, month-end",
            similarity=0.92,
            rerank_score=0.95,
            confidence=0.88,
            usage_count=5,
        )
        assert hit.title == "Advance Property Date Fix"
        assert hit.rerank_score == 0.95
        assert hit.confidence == 0.88
        assert hit.usage_count == 5


class TestSourceDetail:
    """Test source detail enrichment models."""

    def test_kb_detail(self):
        detail = SourceDetail(
            source_type="KB",
            source_id="KB-SYN-0001",
            title="Advance Property Date Fix",
            lineage_ticket="CS-38908386",
            lineage_conversation="CONV-O2RAK1VRJN",
            lineage_script="SCRIPT-0293",
        )
        assert detail.lineage_ticket == "CS-38908386"
        assert detail.lineage_script == "SCRIPT-0293"

    def test_script_detail(self):
        detail = SourceDetail(
            source_type="SCRIPT",
            source_id="SCRIPT-0293",
            script_purpose="Run this backend data-fix script...",
            script_inputs="<DATABASE>, <SITE_NAME>",
        )
        assert detail.script_purpose is not None
        assert detail.script_inputs is not None

    def test_ticket_detail(self):
        detail = SourceDetail(
            source_type="TICKET_RESOLUTION",
            source_id="CS-38908386",
            ticket_subject="Unable to advance property date",
            ticket_resolution="Applied backend data-fix script.",
            ticket_root_cause="Data inconsistency requiring backend fix",
        )
        assert detail.ticket_subject is not None


class TestCitation:
    """Test citation models."""

    def test_citation_minimal(self):
        cite = Citation(source_type="SCRIPT", source_id="SCRIPT-0293")
        assert cite.source_type == "SCRIPT"
        assert cite.title == ""
        assert cite.quote is None

    def test_citation_full(self):
        cite = Citation(
            source_type="KB",
            source_id="KB-SYN-0001",
            title="Advance Property Date Fix",
            quote="Apply the backend data-fix script to resolve...",
        )
        assert cite.title == "Advance Property Date Fix"
        assert "backend" in cite.quote


class TestRagResult:
    """Test RAG result models."""

    def test_success_result(self):
        citations = [
            Citation(
                source_type="SCRIPT",
                source_id="SCRIPT-0293",
                title="Date Advance Fix",
            )
        ]
        result = RagResult(
            question="How do I advance the property date?",
            answer="Use SCRIPT-0293 to advance the property date...",
            citations=citations,
            status=RagStatus.SUCCESS,
            evidence_count=5,
            retrieval_queries=["advance property date", "date advance script"],
        )
        assert result.status == RagStatus.SUCCESS
        assert len(result.citations) == 1
        assert result.evidence_count == 5

    def test_to_context(self):
        citations = [
            Citation(
                source_type="SCRIPT",
                source_id="SCRIPT-0293",
                title="Date Advance Fix",
            ),
            Citation(
                source_type="KB",
                source_id="KB-SYN-0001",
                title="Property Date KB",
            ),
        ]
        result = RagResult(
            question="test",
            answer="The answer is...",
            citations=citations,
            status=RagStatus.SUCCESS,
        )
        context = result.to_context()
        assert "The answer is..." in context
        assert "SCRIPT: Date Advance Fix (SCRIPT-0293)" in context
        assert "KB: Property Date KB (KB-SYN-0001)" in context

    def test_error_result(self):
        result = RagResult(
            question="test",
            answer="Error processing question: timeout",
            citations=[],
            status=RagStatus.ERROR,
        )
        assert result.status == RagStatus.ERROR
        assert "Error" in result.answer


class TestRagState:
    """Test RAG state management."""

    def test_initial_state(self):
        input_data = RagInput(question="test question")
        state = RagState(input=input_data)
        assert state.retrieval_plan is None
        assert state.candidates == []
        assert state.evidence == []
        assert state.source_details == []
        assert state.answer is None
        assert state.validation_passed is False
        assert state.attempt == 0
        assert state.top_k == 10

    def test_state_with_evidence(self):
        input_data = RagInput(question="test question")
        evidence = [
            CorpusHit(
                source_type="SCRIPT",
                source_id="SCRIPT-0001",
                content="Script content",
                similarity=0.9,
            )
        ]
        state = RagState(
            input=input_data,
            evidence=evidence,
            answer="The answer",
            validation_passed=True,
            status=RagStatus.SUCCESS,
        )
        assert len(state.evidence) == 1
        assert state.validation_passed


class TestGapDetection:
    """Test gap detection models."""

    def test_knowledge_decision_types(self):
        assert KnowledgeDecisionType.SAME_KNOWLEDGE == "SAME_KNOWLEDGE"
        assert KnowledgeDecisionType.CONTRADICTS == "CONTRADICTS"
        assert KnowledgeDecisionType.NEW_KNOWLEDGE == "NEW_KNOWLEDGE"

    def test_knowledge_decision(self):
        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
            reasoning="No matching entries found above threshold.",
            similarity_score=0.42,
        )
        assert decision.decision == KnowledgeDecisionType.NEW_KNOWLEDGE
        assert decision.best_match_source_id is None
        assert decision.similarity_score == 0.42

    def test_gap_detection_input(self):
        input_data = GapDetectionInput(
            ticket_number="CS-38908386",
            conversation_id="CONV-O2RAK1VRJN",
            category="Advance Property Date",
            subject="Unable to advance property date",
            resolution="Applied backend data-fix script.",
            root_cause="Data inconsistency requiring backend fix",
            script_id="SCRIPT-0293",
        )
        assert input_data.ticket_number == "CS-38908386"
        assert input_data.category == "Advance Property Date"

    def test_gap_detection_result(self):
        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
            reasoning="No matching entries",
            similarity_score=0.0,
        )
        result = GapDetectionResult(
            decision=decision,
            query_used="Unable to advance property date. Data inconsistency.",
        )
        assert result.decision.decision == KnowledgeDecisionType.NEW_KNOWLEDGE
        assert result.retrieved_entries == []
        assert result.query_used != ""


class TestRetrievalLog:
    """Test retrieval log models."""

    def test_retrieval_outcome_enum(self):
        assert RetrievalOutcome.RESOLVED == "RESOLVED"
        assert RetrievalOutcome.UNHELPFUL == "UNHELPFUL"
        assert RetrievalOutcome.PARTIAL == "PARTIAL"

    def test_retrieval_log_entry(self):
        entry = RetrievalLogEntry(
            retrieval_id="RET-abc123",
            ticket_number="CS-38908386",
            attempt_number=1,
            query_text="advance property date",
            source_type="SCRIPT",
            source_id="SCRIPT-0293",
            similarity_score=0.85,
            outcome=RetrievalOutcome.RESOLVED,
        )
        assert entry.retrieval_id == "RET-abc123"
        assert entry.ticket_number == "CS-38908386"
        assert entry.outcome == RetrievalOutcome.RESOLVED

    def test_retrieval_log_defaults(self):
        entry = RetrievalLogEntry(retrieval_id="RET-test")
        assert entry.ticket_number is None
        assert entry.attempt_number == 1
        assert entry.outcome == RetrievalOutcome.PARTIAL
