"""Tests for the self-learning pipeline (learning_service.py).

All external dependencies (Supabase, LLM, Embedder, RAG graph) are mocked.
Zero network/DB calls required.
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.models.corpus import (
    GapDetectionResult,
    KnowledgeDecision,
    KnowledgeDecisionType,
)
from app.schemas.learning import (
    ConfidenceUpdate,
    KBDraftFromGap,
    LearningEventRecord,
    RetrievalLogEntry,
    ReviewDecision,
)
from app.services.learning_service import (
    _apply_contradiction_approval,
    _build_gap_description,
    _build_log_summary,
    _create_lineage_records,
    _embed_kb_article,
    _fetch_retrieval_logs,
    _fetch_ticket_and_conversation,
    _handle_contradiction,
    _handle_new_knowledge,
    _handle_same_knowledge,
    _link_logs_to_ticket,
    _set_bulk_outcomes,
    _update_confidence_scores,
    review_learning_event,
    run_post_conversation_learning,
)

# All patches target the import location inside learning_service
SVC = "app.services.learning_service"


# ── Group A: Stage 0 — Link Logs & Set Outcomes ─────────────────────


class TestLinkLogsToTicket:
    """A1-A2: _link_logs_to_ticket."""

    @patch(f"{SVC}.get_supabase")
    def test_link_logs_to_ticket(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase
        _link_logs_to_ticket("conv-123", "CS-TEST01")

        mock_supabase.table.assert_called_with("retrieval_log")
        tbl = mock_supabase.table("retrieval_log")
        tbl.update.assert_called_once_with({"ticket_number": "CS-TEST01"})
        tbl.eq.assert_any_call("conversation_id", "conv-123")
        tbl.is_.assert_any_call("ticket_number", "null")
        tbl.execute.assert_called()

    @patch(f"{SVC}.get_supabase")
    def test_link_logs_swallows_exception(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase
        tbl = mock_supabase.table("retrieval_log")
        tbl.execute.side_effect = Exception("DB down")

        # Should NOT raise
        _link_logs_to_ticket("conv-123", "CS-TEST01")


class TestSetBulkOutcomes:
    """A3-A4: _set_bulk_outcomes."""

    @patch(f"{SVC}.get_supabase")
    def test_set_bulk_outcomes_resolved(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase
        _set_bulk_outcomes("CS-TEST01", resolved=True)

        tbl = mock_supabase.table("retrieval_log")
        tbl.update.assert_called_once_with({"outcome": "RESOLVED"})

    @patch(f"{SVC}.get_supabase")
    def test_set_bulk_outcomes_unhelpful(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase
        _set_bulk_outcomes("CS-TEST01", resolved=False)

        tbl = mock_supabase.table("retrieval_log")
        tbl.update.assert_called_once_with({"outcome": "UNHELPFUL"})


# ── Group B: Stage 1 — Fetch & Score Retrieval Logs ─────────────────


class TestFetchRetrievalLogs:
    """B1-B2: _fetch_retrieval_logs."""

    @patch(f"{SVC}.get_supabase")
    def test_returns_entries(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase
        tbl = mock_supabase.table("retrieval_log")
        tbl.execute.return_value = MagicMock(
            data=[
                {
                    "retrieval_id": "RL-001",
                    "ticket_number": "CS-TEST01",
                    "attempt_number": 1,
                    "query_text": "q1",
                    "source_type": "SCRIPT",
                    "source_id": "SCRIPT-001",
                    "similarity_score": 0.85,
                    "outcome": "RESOLVED",
                },
                {
                    "retrieval_id": "RL-002",
                    "ticket_number": "CS-TEST01",
                    "attempt_number": 2,
                    "query_text": "q2",
                    "source_type": "KB",
                    "source_id": "KB-001",
                    "similarity_score": 0.72,
                    "outcome": "PARTIAL",
                },
                {
                    "retrieval_id": "RL-003",
                    "ticket_number": "CS-TEST01",
                    "attempt_number": 3,
                    "query_text": "q3",
                    "source_type": "KB",
                    "source_id": "KB-002",
                    "similarity_score": 0.40,
                    "outcome": "UNHELPFUL",
                },
            ]
        )

        result = _fetch_retrieval_logs("CS-TEST01")
        assert len(result) == 3
        assert all(isinstance(r, RetrievalLogEntry) for r in result)

    @patch(f"{SVC}.get_supabase")
    def test_empty_returns_empty_list(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase
        tbl = mock_supabase.table("retrieval_log")
        tbl.execute.return_value = MagicMock(data=[])

        result = _fetch_retrieval_logs("CS-TEST01")
        assert result == []


class TestUpdateConfidenceScores:
    """B3-B7: _update_confidence_scores."""

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_resolved_delta(self, mock_get_sb, mock_get_settings, mock_supabase, mock_settings):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_supabase.rpc.return_value.execute.return_value = MagicMock(
            data=[{"new_confidence": 0.95, "new_usage_count": 4}]
        )

        log = RetrievalLogEntry(
            retrieval_id="RL-001",
            ticket_number="CS-TEST01",
            attempt_number=1,
            query_text="q1",
            source_type="SCRIPT",
            source_id="SCRIPT-001",
            outcome="RESOLVED",
        )

        result = _update_confidence_scores([log])

        mock_supabase.rpc.assert_called_once_with(
            "update_corpus_confidence",
            {
                "p_source_type": "SCRIPT",
                "p_source_id": "SCRIPT-001",
                "p_delta": 0.10,
                "p_increment_usage": True,
            },
        )
        assert len(result) == 1
        assert result[0] == ConfidenceUpdate(
            source_type="SCRIPT",
            source_id="SCRIPT-001",
            delta=0.10,
            new_confidence=0.95,
            new_usage_count=4,
        )

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_partial_delta(self, mock_get_sb, mock_get_settings, mock_supabase, mock_settings):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_supabase.rpc.return_value.execute.return_value = MagicMock(
            data=[{"new_confidence": 0.52, "new_usage_count": 2}]
        )

        log = RetrievalLogEntry(
            retrieval_id="RL-002",
            ticket_number="CS-TEST01",
            attempt_number=2,
            query_text="q2",
            source_type="KB",
            source_id="KB-001",
            outcome="PARTIAL",
        )

        result = _update_confidence_scores([log])

        mock_supabase.rpc.assert_called_once_with(
            "update_corpus_confidence",
            {
                "p_source_type": "KB",
                "p_source_id": "KB-001",
                "p_delta": 0.02,
                "p_increment_usage": False,
            },
        )
        assert result[0].delta == 0.02

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_unhelpful_delta(self, mock_get_sb, mock_get_settings, mock_supabase, mock_settings):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_supabase.rpc.return_value.execute.return_value = MagicMock(
            data=[{"new_confidence": 0.45, "new_usage_count": 1}]
        )

        log = RetrievalLogEntry(
            retrieval_id="RL-003",
            ticket_number="CS-TEST01",
            attempt_number=3,
            query_text="q3",
            source_type="KB",
            source_id="KB-002",
            outcome="UNHELPFUL",
        )

        result = _update_confidence_scores([log])

        mock_supabase.rpc.assert_called_once_with(
            "update_corpus_confidence",
            {
                "p_source_type": "KB",
                "p_source_id": "KB-002",
                "p_delta": -0.05,
                "p_increment_usage": False,
            },
        )
        assert result[0].delta == -0.05

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_skips_null_fields(self, mock_get_sb, mock_get_settings, mock_supabase, mock_settings):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings

        log = RetrievalLogEntry(
            retrieval_id="RL-004",
            ticket_number="CS-TEST01",
            attempt_number=1,
            query_text="q4",
            source_type=None,
            source_id=None,
            outcome="RESOLVED",
        )

        result = _update_confidence_scores([log])
        assert result == []
        mock_supabase.rpc.assert_not_called()

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_skips_unknown_outcome(
        self, mock_get_sb, mock_get_settings, mock_supabase, mock_settings
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings

        log = RetrievalLogEntry(
            retrieval_id="RL-005",
            ticket_number="CS-TEST01",
            attempt_number=1,
            query_text="q5",
            source_type="SCRIPT",
            source_id="SCRIPT-002",
            outcome=None,
        )

        result = _update_confidence_scores([log])
        assert result == []
        mock_supabase.rpc.assert_not_called()


class TestBuildLogSummary:
    """B8-B10: _build_log_summary."""

    def test_with_outcomes(self, sample_retrieval_logs):
        result = _build_log_summary(sample_retrieval_logs)
        assert result is not None
        assert "3 retrieval attempts" in result
        assert "advance property date" in result

    def test_empty_logs(self):
        result = _build_log_summary([])
        assert result is None

    def test_no_outcomes(self):
        logs = [
            RetrievalLogEntry(
                retrieval_id="RL-X",
                attempt_number=1,
                query_text="test query",
                outcome=None,
            ),
        ]
        result = _build_log_summary(logs)
        assert result is not None
        assert "no outcomes recorded yet" in result


# ── Group C: Stage 2 — Fetch Ticket & Conversation Data ─────────────


class TestFetchTicketAndConversation:
    """C1-C3: _fetch_ticket_and_conversation."""

    @patch(f"{SVC}.get_supabase")
    def test_returns_both(self, mock_get_sb, mock_supabase, sample_ticket_data, sample_conv_data):
        mock_get_sb.return_value = mock_supabase

        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=sample_ticket_data)

        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        ticket, conv = _fetch_ticket_and_conversation("CS-TEST01")
        assert ticket["ticket_number"] == "CS-TEST01"
        assert conv["conversation_id"] == "conv-123"

    @patch(f"{SVC}.get_supabase")
    def test_ticket_missing_graceful(self, mock_get_sb, mock_supabase, sample_conv_data):
        mock_get_sb.return_value = mock_supabase

        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=None)

        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        ticket, conv = _fetch_ticket_and_conversation("CS-TEST01")
        assert ticket == {}
        assert conv["conversation_id"] == "conv-123"

    @patch(f"{SVC}.get_supabase")
    def test_both_missing(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase

        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=None)

        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=None)

        ticket, conv = _fetch_ticket_and_conversation("CS-TEST01")
        assert ticket == {}
        assert conv == {}


# ── Group D: Stage 3 — Handle Classifications ───────────────────────


class TestHandleSameKnowledge:
    """D1-D2: _handle_same_knowledge."""

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_creates_confirmed_event(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_supabase,
        mock_settings,
        sample_gap_result_same,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings

        event_id = _handle_same_knowledge(
            "CS-TEST01", sample_gap_result_same, sample_ticket_data, sample_conv_data
        )

        assert re.match(r"LE-[0-9a-f]{12}", event_id)

        # learning_events insert
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.insert.assert_called_once()
        insert_data = le_tbl.insert.call_args[0][0]
        assert insert_data["event_type"] == "CONFIRMED"
        assert insert_data["final_status"] == "Approved"
        assert insert_data["reviewer_role"] == "System"

        # RPC called with KB boost
        mock_supabase.rpc.assert_called_once_with(
            "update_corpus_confidence",
            {
                "p_source_type": "KB",
                "p_source_id": "KB-001",
                "p_delta": 0.10,
                "p_increment_usage": True,
            },
        )

        # kb_lineage insert
        lineage_tbl = mock_supabase.table("kb_lineage")
        lineage_tbl.insert.assert_called_once()
        lineage_data = lineage_tbl.insert.call_args[0][0]
        assert lineage_data["relationship"] == "REFERENCES"

    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    def test_unknown_match_skips_boost(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_supabase,
        mock_settings,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings

        gap = GapDetectionResult(
            decision=KnowledgeDecision(
                decision=KnowledgeDecisionType.SAME_KNOWLEDGE,
                reasoning="Matched but source unknown",
                best_match_source_id=None,
                similarity_score=0.80,
            ),
        )

        event_id = _handle_same_knowledge(
            "CS-TEST01", gap, sample_ticket_data, sample_conv_data
        )

        assert re.match(r"LE-[0-9a-f]{12}", event_id)
        # RPC should NOT be called when best_match is unknown
        mock_supabase.rpc.assert_not_called()

        # Lineage still created with "unknown"
        lineage_tbl = mock_supabase.table("kb_lineage")
        lineage_tbl.insert.assert_called_once()
        lineage_data = lineage_tbl.insert.call_args[0][0]
        assert lineage_data["kb_article_id"] == "unknown"


class TestHandleNewKnowledge:
    """D3: _handle_new_knowledge."""

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.get_supabase")
    async def test_drafts_kb(
        self,
        mock_get_sb,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        sample_kb_draft,
        sample_ticket_data,
        sample_conv_data,
        sample_retrieval_logs,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_gen_output.return_value = sample_kb_draft

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        event_id, kb_id = await _handle_new_knowledge(
            "CS-TEST01", sample_ticket_data, sample_conv_data, sample_retrieval_logs
        )

        assert re.match(r"LE-[0-9a-f]{12}", event_id)
        assert re.match(r"KB-SYN-[0-9A-F]{8}", kb_id)

        # knowledge_articles insert
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.insert.assert_called_once()
        ka_data = ka_tbl.insert.call_args[0][0]
        assert ka_data["status"] == "Draft"
        assert ka_data["source_type"] == "SYNTH_FROM_TICKET"
        assert ka_data["title"] == "How to Advance Property Date"

        # learning_events insert
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.insert.assert_called_once()
        le_data = le_tbl.insert.call_args[0][0]
        assert le_data["event_type"] == "GAP"
        assert le_data["final_status"] is None

        # kb_lineage insert (3 records)
        lineage_tbl = mock_supabase.table("kb_lineage")
        lineage_tbl.insert.assert_called_once()
        lineage_records = lineage_tbl.insert.call_args[0][0]
        assert len(lineage_records) == 3

        # retrieval_corpus insert
        corpus_tbl = mock_supabase.table("retrieval_corpus")
        corpus_tbl.insert.assert_called_once()
        corpus_data = corpus_tbl.insert.call_args[0][0]
        assert corpus_data["confidence"] == 0.5
        assert corpus_data["usage_count"] == 0
        assert len(corpus_data["embedding"]) == 3072


class TestHandleContradiction:
    """D4-D5: _handle_contradiction."""

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.get_supabase")
    async def test_drafts_replacement(
        self,
        mock_get_sb,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        sample_kb_draft,
        sample_gap_result_contradiction,
        sample_ticket_data,
        sample_conv_data,
        sample_retrieval_logs,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_gen_output.return_value = sample_kb_draft

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        # Mock existing KB fetch for contradiction
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(
            data={"title": "Old KB", "body": "Old content"}
        )

        event_id, kb_id = await _handle_contradiction(
            "CS-TEST01",
            sample_gap_result_contradiction,
            sample_ticket_data,
            sample_conv_data,
            sample_retrieval_logs,
        )

        assert re.match(r"LE-[0-9a-f]{12}", event_id)
        assert re.match(r"KB-SYN-[0-9A-F]{8}", kb_id)

        # learning_events insert has CONTRADICTION type + flagged id
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.insert.assert_called_once()
        le_data = le_tbl.insert.call_args[0][0]
        assert le_data["event_type"] == "CONTRADICTION"
        assert le_data["flagged_kb_article_id"] == "KB-OLD"

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.get_supabase")
    async def test_missing_existing_kb_still_drafts(
        self,
        mock_get_sb,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        sample_kb_draft,
        sample_gap_result_contradiction,
        sample_ticket_data,
        sample_conv_data,
        sample_retrieval_logs,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_gen_output.return_value = sample_kb_draft

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        # Make KB fetch raise on first call, succeed on subsequent calls
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.side_effect = [
            Exception("KB not found"),       # select existing KB → caught by try/except
            MagicMock(data={}),              # insert draft KB article
        ]

        # Should NOT crash
        event_id, kb_id = await _handle_contradiction(
            "CS-TEST01",
            sample_gap_result_contradiction,
            sample_ticket_data,
            sample_conv_data,
            sample_retrieval_logs,
        )

        assert re.match(r"LE-[0-9a-f]{12}", event_id)
        assert re.match(r"KB-SYN-[0-9A-F]{8}", kb_id)


# ── Group E: Full Pipeline Orchestration ─────────────────────────────


class TestFullPipeline:
    """E1-E5: run_post_conversation_learning."""

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.run_gap_detection")
    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    async def test_same_knowledge(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_run_gap,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        mock_settings,
        sample_gap_result_same,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_run_gap.return_value = sample_gap_result_same

        # Mock retrieval_log fetch: 2 entries
        rl_tbl = mock_supabase.table("retrieval_log")
        rl_tbl.execute.return_value = MagicMock(
            data=[
                {
                    "retrieval_id": "RL-001",
                    "ticket_number": "CS-TEST01",
                    "attempt_number": 1,
                    "query_text": "q1",
                    "source_type": "SCRIPT",
                    "source_id": "SCRIPT-001",
                    "outcome": "RESOLVED",
                },
            ]
        )

        # Mock RPC
        mock_supabase.rpc.return_value.execute.return_value = MagicMock(
            data=[{"new_confidence": 0.95, "new_usage_count": 4}]
        )

        # Mock ticket/conversation fetch
        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=sample_ticket_data)
        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        result = await run_post_conversation_learning(
            "CS-TEST01", resolved=True, conversation_id="conv-123"
        )

        assert result.gap_classification == KnowledgeDecisionType.SAME_KNOWLEDGE
        assert result.drafted_kb_article_id is None
        assert result.matched_kb_article_id == "KB-001"
        assert result.retrieval_logs_processed == 1

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.run_gap_detection")
    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    async def test_new_knowledge(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_run_gap,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        mock_settings,
        sample_gap_result_new,
        sample_kb_draft,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_run_gap.return_value = sample_gap_result_new
        mock_gen_output.return_value = sample_kb_draft

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        # Empty retrieval logs
        rl_tbl = mock_supabase.table("retrieval_log")
        rl_tbl.execute.return_value = MagicMock(data=[])

        # Mock ticket/conversation fetch
        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=sample_ticket_data)
        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        result = await run_post_conversation_learning(
            "CS-TEST01", resolved=True, conversation_id="conv-123"
        )

        assert result.gap_classification == KnowledgeDecisionType.NEW_KNOWLEDGE
        assert result.drafted_kb_article_id is not None
        assert re.match(r"KB-SYN-[0-9A-F]{8}", result.drafted_kb_article_id)
        assert result.matched_kb_article_id is None

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.run_gap_detection")
    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    async def test_contradicts(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_run_gap,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        mock_settings,
        sample_gap_result_contradiction,
        sample_kb_draft,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_run_gap.return_value = sample_gap_result_contradiction
        mock_gen_output.return_value = sample_kb_draft

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        # Empty retrieval logs
        rl_tbl = mock_supabase.table("retrieval_log")
        rl_tbl.execute.return_value = MagicMock(data=[])

        # Mock ticket/conversation
        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=sample_ticket_data)
        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        # Mock existing KB fetch for contradiction handler
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(
            data={"title": "Old KB", "body": "Old content"}
        )

        result = await run_post_conversation_learning(
            "CS-TEST01", resolved=True, conversation_id="conv-123"
        )

        assert result.gap_classification == KnowledgeDecisionType.CONTRADICTS
        assert result.drafted_kb_article_id is not None
        assert result.matched_kb_article_id == "KB-OLD"

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.run_gap_detection")
    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    async def test_no_conversation_id_skips_link(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_run_gap,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        mock_settings,
        sample_gap_result_same,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_run_gap.return_value = sample_gap_result_same

        # Empty logs
        rl_tbl = mock_supabase.table("retrieval_log")
        rl_tbl.execute.return_value = MagicMock(data=[])

        # Mock ticket/conversation
        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=sample_ticket_data)
        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=[])

        result = await run_post_conversation_learning(
            "CS-TEST01", resolved=True, conversation_id=None
        )

        # _link_logs_to_ticket should NOT have been called — verify retrieval_log
        # was only called for the fetch (select), not for update with conversation_id
        # The first call to retrieval_log.update should be _set_bulk_outcomes only
        rl_tbl = mock_supabase.table("retrieval_log")
        for call in rl_tbl.update.call_args_list:
            data = call[0][0]
            # Should only have "outcome" updates, not "ticket_number" linking
            assert "ticket_number" not in data

    @pytest.mark.asyncio
    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.generate_structured_output", new_callable=AsyncMock)
    @patch(f"{SVC}.run_gap_detection")
    @patch(f"{SVC}.get_settings")
    @patch(f"{SVC}.get_supabase")
    async def test_no_retrieval_logs(
        self,
        mock_get_sb,
        mock_get_settings,
        mock_run_gap,
        mock_gen_output,
        mock_embedder_cls,
        mock_supabase,
        mock_settings,
        sample_gap_result_same,
        sample_ticket_data,
        sample_conv_data,
    ):
        mock_get_sb.return_value = mock_supabase
        mock_get_settings.return_value = mock_settings
        mock_run_gap.return_value = sample_gap_result_same

        # Empty logs
        rl_tbl = mock_supabase.table("retrieval_log")
        rl_tbl.execute.return_value = MagicMock(data=[])

        # Mock ticket/conversation
        tickets_tbl = mock_supabase.table("tickets")
        tickets_tbl.execute.return_value = MagicMock(data=sample_ticket_data)
        convs_tbl = mock_supabase.table("conversations")
        convs_tbl.execute.return_value = MagicMock(data=sample_conv_data)

        mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=[])

        result = await run_post_conversation_learning(
            "CS-TEST01", resolved=True, conversation_id="conv-123"
        )

        assert result.confidence_updates == []
        assert result.retrieval_logs_processed == 0
        # Gap detection still runs
        mock_run_gap.assert_called_once()


# ── Group F: Review Learning Event ───────────────────────────────────


class TestReviewLearningEvent:
    """F1-F5: review_learning_event."""

    @pytest.mark.asyncio
    @patch(f"{SVC}.get_supabase")
    async def test_approve_gap_event(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase

        # learning_events: fetch -> update -> fetch_updated (3 execute calls)
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.execute.side_effect = [
            MagicMock(
                data={
                    "event_id": "LE-aaaaaaaaaaaa",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Gap detected",
                    "event_type": "GAP",
                    "proposed_kb_article_id": "KB-SYN-TEST01",
                    "flagged_kb_article_id": None,
                    "draft_summary": "Test draft",
                    "final_status": None,
                    "reviewer_role": None,
                    "event_timestamp": None,
                }
            ),
            MagicMock(data={}),  # update result
            MagicMock(
                data={
                    "event_id": "LE-aaaaaaaaaaaa",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Gap detected",
                    "event_type": "GAP",
                    "proposed_kb_article_id": "KB-SYN-TEST01",
                    "flagged_kb_article_id": None,
                    "draft_summary": "Test draft",
                    "final_status": "Approved",
                    "reviewer_role": "Tier 3 Support",
                    "event_timestamp": "2026-01-01T00:00:00",
                }
            ),
        ]

        # knowledge_articles: update KB to Active (1 execute call)
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(data={})

        decision = ReviewDecision(decision="Approved", reviewer_role="Tier 3 Support")
        result = await review_learning_event("LE-aaaaaaaaaaaa", decision)

        # learning_events update called with Approved
        le_tbl.update.assert_called()
        update_calls = le_tbl.update.call_args_list
        assert any(
            call[0][0].get("final_status") == "Approved" for call in update_calls
        )

        # knowledge_articles update to Active
        ka_tbl.update.assert_called_once()
        ka_update_data = ka_tbl.update.call_args[0][0]
        assert ka_update_data["status"] == "Active"

    @pytest.mark.asyncio
    @patch(f"{SVC}.get_supabase")
    async def test_reject_gap_event(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase

        # learning_events: fetch -> update -> fetch_updated (3 calls)
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.execute.side_effect = [
            MagicMock(
                data={
                    "event_id": "LE-aaaaaaaaaaaa",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Gap detected",
                    "event_type": "GAP",
                    "proposed_kb_article_id": "KB-SYN-TEST01",
                    "flagged_kb_article_id": None,
                    "draft_summary": "Test draft",
                    "final_status": None,
                    "reviewer_role": None,
                    "event_timestamp": None,
                }
            ),
            MagicMock(data={}),  # update
            MagicMock(
                data={
                    "event_id": "LE-aaaaaaaaaaaa",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Gap detected",
                    "event_type": "GAP",
                    "proposed_kb_article_id": "KB-SYN-TEST01",
                    "flagged_kb_article_id": None,
                    "draft_summary": "Test draft",
                    "final_status": "Rejected",
                    "reviewer_role": "Tier 3 Support",
                    "event_timestamp": "2026-01-01T00:00:00",
                }
            ),
        ]

        # knowledge_articles: archive KB (1 call)
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(data={})

        # retrieval_corpus: delete (1 call)
        corpus_tbl = mock_supabase.table("retrieval_corpus")
        corpus_tbl.execute.return_value = MagicMock(data={})

        decision = ReviewDecision(decision="Rejected", reviewer_role="Tier 3 Support")
        result = await review_learning_event("LE-aaaaaaaaaaaa", decision)

        # knowledge_articles archived
        ka_tbl.update.assert_called_once()
        assert ka_tbl.update.call_args[0][0]["status"] == "Archived"

        # retrieval_corpus delete called
        corpus_tbl.delete.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{SVC}._apply_contradiction_approval")
    @patch(f"{SVC}.get_supabase")
    async def test_approve_contradiction_event(
        self, mock_get_sb, mock_apply, mock_supabase
    ):
        mock_get_sb.return_value = mock_supabase

        le_tbl = mock_supabase.table("learning_events")
        le_tbl.execute.side_effect = [
            MagicMock(
                data={
                    "event_id": "LE-bbbbbbbbbbbb",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Contradiction found",
                    "event_type": "CONTRADICTION",
                    "proposed_kb_article_id": "KB-NEW",
                    "flagged_kb_article_id": "KB-OLD",
                    "draft_summary": "Replacement draft",
                    "final_status": None,
                    "reviewer_role": None,
                    "event_timestamp": None,
                }
            ),
            MagicMock(data={}),  # update
            MagicMock(
                data={
                    "event_id": "LE-bbbbbbbbbbbb",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Contradiction found",
                    "event_type": "CONTRADICTION",
                    "proposed_kb_article_id": "KB-NEW",
                    "flagged_kb_article_id": "KB-OLD",
                    "draft_summary": "Replacement draft",
                    "final_status": "Approved",
                    "reviewer_role": "Support Ops Review",
                    "event_timestamp": "2026-01-01T00:00:00",
                }
            ),
        ]

        decision = ReviewDecision(
            decision="Approved", reviewer_role="Support Ops Review"
        )
        result = await review_learning_event("LE-bbbbbbbbbbbb", decision)

        # _apply_contradiction_approval called with correct args
        mock_apply.assert_called_once()
        args = mock_apply.call_args[0]
        assert args[0] == "KB-OLD"
        assert args[1] == "KB-NEW"

    @pytest.mark.asyncio
    @patch(f"{SVC}.get_supabase")
    async def test_reject_contradiction_event(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase

        # learning_events: fetch -> update -> fetch_updated (3 calls)
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.execute.side_effect = [
            MagicMock(
                data={
                    "event_id": "LE-bbbbbbbbbbbb",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Contradiction found",
                    "event_type": "CONTRADICTION",
                    "proposed_kb_article_id": "KB-NEW",
                    "flagged_kb_article_id": "KB-OLD",
                    "draft_summary": "Replacement draft",
                    "final_status": None,
                    "reviewer_role": None,
                    "event_timestamp": None,
                }
            ),
            MagicMock(data={}),  # update
            MagicMock(
                data={
                    "event_id": "LE-bbbbbbbbbbbb",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Contradiction found",
                    "event_type": "CONTRADICTION",
                    "proposed_kb_article_id": "KB-NEW",
                    "flagged_kb_article_id": "KB-OLD",
                    "draft_summary": "Replacement draft",
                    "final_status": "Rejected",
                    "reviewer_role": "Tier 3 Support",
                    "event_timestamp": "2026-01-01T00:00:00",
                }
            ),
        ]

        # knowledge_articles: archive draft (1 call)
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(data={})

        # retrieval_corpus: delete draft (1 call)
        corpus_tbl = mock_supabase.table("retrieval_corpus")
        corpus_tbl.execute.return_value = MagicMock(data={})

        decision = ReviewDecision(decision="Rejected", reviewer_role="Tier 3 Support")
        result = await review_learning_event("LE-bbbbbbbbbbbb", decision)

        # Draft archived
        ka_tbl.update.assert_called_once()
        assert ka_tbl.update.call_args[0][0]["status"] == "Archived"

        # Draft removed from corpus
        corpus_tbl.delete.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{SVC}.get_supabase")
    async def test_returns_updated_record(self, mock_get_sb, mock_supabase):
        mock_get_sb.return_value = mock_supabase

        final_data = {
            "event_id": "LE-aaaaaaaaaaaa",
            "trigger_ticket_number": "CS-TEST01",
            "detected_gap": "Gap detected",
            "event_type": "GAP",
            "proposed_kb_article_id": "KB-SYN-TEST01",
            "flagged_kb_article_id": None,
            "draft_summary": "Test draft",
            "final_status": "Approved",
            "reviewer_role": "Tier 3 Support",
            "event_timestamp": "2026-01-01T00:00:00",
        }

        # learning_events: fetch -> update -> fetch_updated (3 calls)
        le_tbl = mock_supabase.table("learning_events")
        le_tbl.execute.side_effect = [
            MagicMock(
                data={
                    "event_id": "LE-aaaaaaaaaaaa",
                    "trigger_ticket_number": "CS-TEST01",
                    "detected_gap": "Gap detected",
                    "event_type": "GAP",
                    "proposed_kb_article_id": "KB-SYN-TEST01",
                    "flagged_kb_article_id": None,
                    "draft_summary": "Test draft",
                    "final_status": None,
                    "reviewer_role": None,
                    "event_timestamp": None,
                }
            ),
            MagicMock(data={}),  # update
            MagicMock(data=final_data),  # final fetch
        ]

        # knowledge_articles: activate KB (1 call)
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(data={})

        decision = ReviewDecision(decision="Approved", reviewer_role="Tier 3 Support")
        result = await review_learning_event("LE-aaaaaaaaaaaa", decision)

        assert isinstance(result, LearningEventRecord)
        assert result.event_id == "LE-aaaaaaaaaaaa"
        assert result.final_status == "Approved"
        assert result.reviewer_role == "Tier 3 Support"


# ── Group G: Helper Functions ────────────────────────────────────────


class TestCreateLineageRecords:
    """G1-G2: _create_lineage_records."""

    @patch(f"{SVC}.get_supabase")
    def test_with_script(self, mock_get_sb, mock_supabase, sample_ticket_data, sample_conv_data):
        mock_get_sb.return_value = mock_supabase

        _create_lineage_records(
            "KB-SYN-TEST01",
            "CS-TEST01",
            sample_ticket_data,
            sample_conv_data,
            "2026-01-01T00:00:00+00:00",
        )

        lineage_tbl = mock_supabase.table("kb_lineage")
        lineage_tbl.insert.assert_called_once()
        records = lineage_tbl.insert.call_args[0][0]
        assert len(records) == 3

        # Ticket record
        assert records[0]["source_type"] == "Ticket"
        assert records[0]["relationship"] == "CREATED_FROM"

        # Conversation record
        assert records[1]["source_type"] == "Conversation"
        assert records[1]["source_id"] == "conv-123"

        # Script record — has script_id so CREATED_FROM
        assert records[2]["source_type"] == "Script"
        assert records[2]["source_id"] == "SCRIPT-001"
        assert records[2]["relationship"] == "CREATED_FROM"

    @patch(f"{SVC}.get_supabase")
    def test_without_script(self, mock_get_sb, mock_supabase, sample_conv_data):
        mock_get_sb.return_value = mock_supabase
        ticket_no_script = {
            "ticket_number": "CS-TEST01",
            "script_id": None,
        }

        _create_lineage_records(
            "KB-SYN-TEST01",
            "CS-TEST01",
            ticket_no_script,
            sample_conv_data,
            "2026-01-01T00:00:00+00:00",
        )

        lineage_tbl = mock_supabase.table("kb_lineage")
        records = lineage_tbl.insert.call_args[0][0]

        # Script record — no script_id so REFERENCES, source_id falls back to ticket_number
        assert records[2]["source_type"] == "Script"
        assert records[2]["source_id"] == "CS-TEST01"
        assert records[2]["relationship"] == "REFERENCES"


class TestEmbedKBArticle:
    """G3: _embed_kb_article."""

    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.get_supabase")
    def test_embeds_correctly(self, mock_get_sb, mock_embedder_cls, mock_supabase, sample_kb_draft):
        mock_get_sb.return_value = mock_supabase

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        _embed_kb_article("KB-SYN-TEST01", sample_kb_draft)

        corpus_tbl = mock_supabase.table("retrieval_corpus")
        corpus_tbl.insert.assert_called_once()
        data = corpus_tbl.insert.call_args[0][0]
        assert data["confidence"] == 0.5
        assert data["usage_count"] == 0
        assert data["source_type"] == "KB"
        assert data["source_id"] == "KB-SYN-TEST01"
        assert len(data["embedding"]) == 3072


class TestApplyContradictionApproval:
    """G4: _apply_contradiction_approval."""

    @patch(f"{SVC}.Embedder")
    @patch(f"{SVC}.get_supabase")
    def test_applies_correctly(self, mock_get_sb, mock_embedder_cls, mock_supabase):
        mock_get_sb.return_value = mock_supabase

        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.2] * 3072

        # Mock draft fetch
        ka_tbl = mock_supabase.table("knowledge_articles")
        ka_tbl.execute.return_value = MagicMock(
            data={
                "title": "New Title",
                "body": "New Body",
                "tags": "tag1,tag2",
                "module": "Module",
                "category": "Category",
            }
        )

        _apply_contradiction_approval("KB-OLD", "KB-NEW", "2026-01-01T00:00:00")

        # Old KB updated with draft content + Active status
        ka_update_calls = ka_tbl.update.call_args_list
        # First update: old KB with new content
        old_kb_update = ka_update_calls[0][0][0]
        assert old_kb_update["title"] == "New Title"
        assert old_kb_update["body"] == "New Body"
        assert old_kb_update["status"] == "Active"

        # Second update: draft archived
        draft_archive = ka_update_calls[1][0][0]
        assert draft_archive["status"] == "Archived"

        # Old KB re-embedded in corpus
        corpus_tbl = mock_supabase.table("retrieval_corpus")
        corpus_tbl.update.assert_called_once()
        corpus_data = corpus_tbl.update.call_args[0][0]
        assert len(corpus_data["embedding"]) == 3072
        assert corpus_data["title"] == "New Title"

        # Draft removed from corpus
        corpus_tbl.delete.assert_called_once()


class TestBuildGapDescription:
    """G5-G6: _build_gap_description."""

    def test_with_logs(self, sample_retrieval_logs):
        result = _build_gap_description(sample_retrieval_logs)
        assert "3 retrieval attempts" in result
        assert "advance property date" in result

    def test_no_logs(self):
        result = _build_gap_description([])
        assert "No retrieval attempts" in result
