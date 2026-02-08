"""Shared fixtures for learning_service tests."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.rag.models.corpus import (
    GapDetectionResult,
    KnowledgeDecision,
    KnowledgeDecisionType,
)
from app.schemas.learning import (
    KBDraftFromGap,
    RetrievalLogEntry,
)


# ── Supabase fluent-API mock ────────────────────────────────────────


def _chain_mock() -> MagicMock:
    """Return a MagicMock where every method returns self (chainable)."""
    m = MagicMock()
    for method in (
        "select",
        "eq",
        "is_",
        "in_",
        "order",
        "maybe_single",
        "single",
        "update",
        "insert",
        "delete",
    ):
        getattr(m, method).return_value = m
    m.execute.return_value = MagicMock(data=[])
    return m


@pytest.fixture
def mock_supabase():
    """Supabase client mock with chainable table API.

    Usage in tests:
        mock_supabase.table("retrieval_log") returns a chainable mock.
        Assign `.execute.return_value.data` to control returned rows.
    """
    sb = MagicMock()
    _tables: dict[str, MagicMock] = {}

    def _table(name: str) -> MagicMock:
        if name not in _tables:
            _tables[name] = _chain_mock()
        return _tables[name]

    sb.table.side_effect = _table
    sb._tables = _tables  # expose for assertions

    # RPC also needs chaining
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data=[])
    sb.rpc.return_value = rpc_chain

    return sb


@pytest.fixture
def mock_settings():
    """Mock Settings with default confidence deltas."""
    s = MagicMock()
    s.confidence_delta_resolved = 0.10
    s.confidence_delta_partial = 0.02
    s.confidence_delta_unhelpful = -0.05
    s.gap_similarity_threshold = 0.75
    return s


# ── Sample data fixtures ────────────────────────────────────────────

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def sample_retrieval_logs():
    return [
        RetrievalLogEntry(
            retrieval_id="RL-001",
            ticket_number="CS-TEST01",
            conversation_id="conv-123",
            attempt_number=1,
            query_text="advance property date",
            source_type="SCRIPT",
            source_id="SCRIPT-001",
            similarity_score=0.85,
            outcome="RESOLVED",
            created_at=NOW,
        ),
        RetrievalLogEntry(
            retrieval_id="RL-002",
            ticket_number="CS-TEST01",
            conversation_id="conv-123",
            attempt_number=2,
            query_text="property date change script",
            source_type="KB",
            source_id="KB-001",
            similarity_score=0.72,
            outcome="PARTIAL",
            created_at=NOW,
        ),
        RetrievalLogEntry(
            retrieval_id="RL-003",
            ticket_number="CS-TEST01",
            conversation_id="conv-123",
            attempt_number=3,
            query_text="date setup instructions",
            source_type="KB",
            source_id="KB-002",
            similarity_score=0.40,
            outcome="UNHELPFUL",
            created_at=NOW,
        ),
    ]


@pytest.fixture
def sample_ticket_data():
    return {
        "ticket_number": "CS-TEST01",
        "subject": "Cannot advance property date",
        "description": "Tenant reports date not advancing",
        "resolution": "Used the date advance wizard",
        "root_cause": "Date configuration was incorrect",
        "module": "Property Management",
        "category": "Advance Property Date",
        "status": "Closed",
        "priority": "Medium",
        "tier": "1",
        "case_type": "How-To",
        "tags": "date,property",
        "script_id": "SCRIPT-001",
        "kb_article_id": None,
    }


@pytest.fixture
def sample_conv_data():
    return {
        "ticket_number": "CS-TEST01",
        "conversation_id": "conv-123",
        "channel": "Chat",
        "customer_role": "Property Manager",
        "agent_name": "Agent Smith",
        "product": "OneSite",
        "category": "Advance Property Date",
        "transcript": "Customer: I can't advance the date.\nAgent: Let me help.",
        "sentiment": "Frustrated",
    }


@pytest.fixture
def sample_gap_result_same():
    return GapDetectionResult(
        decision=KnowledgeDecision(
            decision=KnowledgeDecisionType.SAME_KNOWLEDGE,
            reasoning="Resolution matches existing KB article.",
            best_match_source_id="KB-001",
            similarity_score=0.92,
        ),
        retrieved_entries=[],
        enriched_sources=[],
        query_used="advance property date",
    )


@pytest.fixture
def sample_gap_result_new():
    return GapDetectionResult(
        decision=KnowledgeDecision(
            decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
            reasoning="No existing article covers this resolution.",
            best_match_source_id=None,
            similarity_score=0.30,
        ),
        retrieved_entries=[],
        enriched_sources=[],
        query_used="advance property date",
    )


@pytest.fixture
def sample_gap_result_contradiction():
    return GapDetectionResult(
        decision=KnowledgeDecision(
            decision=KnowledgeDecisionType.CONTRADICTS,
            reasoning="Existing KB article gives wrong steps.",
            best_match_source_id="KB-OLD",
            similarity_score=0.88,
        ),
        retrieved_entries=[],
        enriched_sources=[],
        query_used="advance property date",
    )


@pytest.fixture
def sample_kb_draft():
    return KBDraftFromGap(
        title="How to Advance Property Date",
        body="Step 1: Open the date wizard. Step 2: Select new date. Step 3: Confirm.",
        tags="date,property,advance",
        category="Advance Property Date",
        module="Property Management",
    )
