"""Tests for RAG graph construction and runner functions."""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.agent.graph import (
    create_gap_detection_graph,
    create_rag_graph,
    create_retrieval_graph,
    run_gap_detection,
    run_rag,
    run_rag_retrieval_only,
    should_retry_or_finish,
    _timed_node,
    _write_execution_log,
)
from app.rag.models.corpus import (
    GapDetectionInput,
    KnowledgeDecision,
    KnowledgeDecisionType,
)
from app.rag.models.rag import RagState, RagInput, RagStatus, CorpusHit


# ── should_retry_or_finish ─────────────────────────────────────────────


class TestShouldRetryOrFinish:
    def test_finish_when_validated(self):
        state = RagState(
            input=RagInput(question="q"),
            top_k=5,
            validation_passed=True,
        )
        assert should_retry_or_finish(state) == "finish"

    def test_retry_first_attempt(self):
        state = RagState(
            input=RagInput(question="q"),
            top_k=5,
            validation_passed=False,
            attempt=0,
            status=RagStatus.SUCCESS,
        )
        assert should_retry_or_finish(state) == "retry"

    def test_finish_after_retry(self):
        state = RagState(
            input=RagInput(question="q"),
            top_k=5,
            validation_passed=False,
            attempt=1,
        )
        assert should_retry_or_finish(state) == "finish"

    def test_finish_insufficient_evidence(self):
        state = RagState(
            input=RagInput(question="q"),
            top_k=5,
            validation_passed=False,
            attempt=0,
            status=RagStatus.INSUFFICIENT_EVIDENCE,
        )
        assert should_retry_or_finish(state) == "finish"


# ── Graph creation ─────────────────────────────────────────────────────


class TestGraphCreation:
    def test_create_rag_graph_compiles(self):
        graph = create_rag_graph()
        app = graph.compile()
        assert app is not None

    def test_create_retrieval_graph_compiles(self):
        graph = create_retrieval_graph()
        app = graph.compile()
        assert app is not None

    def test_create_gap_detection_graph_compiles(self):
        latencies = {}
        graph = create_gap_detection_graph(latencies)
        app = graph.compile()
        assert app is not None


# ── _timed_node ────────────────────────────────────────────────────────


class TestTimedNode:
    def test_records_latency(self):
        latencies = {}

        def dummy_node(state):
            return {"value": 42}

        wrapped = _timed_node(dummy_node, latencies)
        result = wrapped({})
        assert result == {"value": 42}
        assert "dummy_node" in latencies
        assert latencies["dummy_node"] >= 0

    def test_preserves_function_name(self):
        latencies = {}

        def my_func(state):
            return {}

        wrapped = _timed_node(my_func, latencies)
        assert wrapped.__name__ == "my_func"


# ── run_rag ────────────────────────────────────────────────────────────


class TestRunRag:
    @patch("app.rag.agent.graph.create_rag_graph")
    def test_success_path(self, mock_create):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph

        from app.rag.models.rag import QueryVariant, RetrievalPlan

        mock_app.invoke.return_value = {
            "retrieval_plan": RetrievalPlan(
                queries=[
                    QueryVariant(query="q1", rationale="r1"),
                    QueryVariant(query="q2", rationale="r2"),
                ]
            ),
            "evidence": [
                CorpusHit(
                    source_type="KB",
                    source_id="KB-001",
                    title="T",
                    content="C",
                    similarity=0.9,
                )
            ],
            "citations": [],
            "answer": "The answer",
            "status": RagStatus.SUCCESS,
        }

        result = run_rag("How to fix?")
        assert result.answer == "The answer"
        assert result.evidence_count == 1
        assert result.retrieval_queries == ["q1", "q2"]
        assert result.status == RagStatus.SUCCESS

    @patch("app.rag.agent.graph.create_rag_graph")
    def test_error_path(self, mock_create):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph
        mock_app.invoke.side_effect = RuntimeError("boom")

        result = run_rag("How to fix?")
        assert result.status == RagStatus.ERROR
        assert "Error" in result.answer
        assert result.evidence_count == 0

    @patch("app.rag.agent.graph.create_rag_graph")
    def test_no_plan_in_state(self, mock_create):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph
        mock_app.invoke.return_value = {
            "evidence": [],
            "citations": [],
            "answer": "No results",
            "status": RagStatus.SUCCESS,
        }

        result = run_rag("q")
        assert result.retrieval_queries == []


# ── run_rag_retrieval_only ─────────────────────────────────────────────


class TestRunRagRetrievalOnly:
    @patch("app.rag.agent.graph.create_retrieval_graph")
    def test_success_path(self, mock_create):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph

        from app.rag.models.rag import QueryVariant, RetrievalPlan

        evidence = [
            CorpusHit(
                source_type="SCRIPT",
                source_id="S-001",
                title="Script",
                content="Content",
                similarity=0.85,
            )
        ]
        mock_app.invoke.return_value = {
            "retrieval_plan": RetrievalPlan(
                queries=[
                    QueryVariant(query="q", rationale="r"),
                    QueryVariant(query="q2", rationale="r2"),
                ]
            ),
            "evidence": evidence,
            "status": RagStatus.SUCCESS,
        }

        result = run_rag_retrieval_only("question", category="General")
        assert result.answer == ""
        assert result.top_hits == evidence
        assert result.evidence_count == 1

    @patch("app.rag.agent.graph.create_retrieval_graph")
    def test_error_path(self, mock_create):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph
        mock_app.invoke.side_effect = RuntimeError("fail")

        result = run_rag_retrieval_only("q")
        assert result.status == RagStatus.ERROR
        assert result.evidence_count == 0


# ── run_gap_detection ──────────────────────────────────────────────────


class TestRunGapDetection:
    @patch("app.rag.agent.graph._write_execution_log")
    @patch("app.rag.agent.graph.create_gap_detection_graph")
    def test_success_path(self, mock_create, mock_log):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph

        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.SAME_KNOWLEDGE,
            reasoning="Already known",
            similarity_score=0.95,
        )
        mock_app.invoke.return_value = {
            "answer": decision.model_dump_json(),
            "evidence": [],
            "source_details": [],
            "status": RagStatus.SUCCESS,
        }

        input_data = GapDetectionInput(
            ticket_number="CS-TEST01",
            subject="Login issue",
            description="Cannot log in",
            resolution="Reset password",
        )
        result = run_gap_detection(input_data)
        assert result.decision.decision == KnowledgeDecisionType.SAME_KNOWLEDGE
        mock_log.assert_called_once()

    @patch("app.rag.agent.graph._write_execution_log")
    @patch("app.rag.agent.graph.create_gap_detection_graph")
    def test_error_falls_back_to_new_knowledge(self, mock_create, mock_log):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph
        mock_app.invoke.side_effect = RuntimeError("boom")

        input_data = GapDetectionInput(
            ticket_number="CS-TEST02",
            subject="New issue",
            description="Something new",
        )
        result = run_gap_detection(input_data)
        assert result.decision.decision == KnowledgeDecisionType.NEW_KNOWLEDGE
        assert "failed" in result.decision.reasoning.lower()

    @patch("app.rag.agent.graph._write_execution_log")
    @patch("app.rag.agent.graph.create_gap_detection_graph")
    def test_query_construction_with_all_fields(self, mock_create, mock_log):
        mock_app = MagicMock()
        mock_graph = MagicMock()
        mock_graph.compile.return_value = mock_app
        mock_create.return_value = mock_graph

        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
            reasoning="New",
            similarity_score=0.3,
        )
        mock_app.invoke.return_value = {
            "answer": decision.model_dump_json(),
            "evidence": [],
            "source_details": [],
        }

        input_data = GapDetectionInput(
            ticket_number="CS-T",
            subject="Subject",
            description="Desc",
            root_cause="Root",
            category="General",
            resolution="Fixed it by doing X" * 20,  # Long resolution
        )
        result = run_gap_detection(input_data)
        assert "Subject" in result.query_used
        assert "Root" in result.query_used


# ── _write_execution_log ───────────────────────────────────────────────


class TestWriteExecutionLog:
    @patch("app.rag.core.get_supabase_client")
    def test_writes_row(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        input_data = GapDetectionInput(
            ticket_number="CS-T",
            subject="S",
            description="D",
        )
        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.SAME_KNOWLEDGE,
            reasoning="r",
            similarity_score=0.9,
        )
        evidence = [
            CorpusHit(
                source_type="KB",
                source_id="KB-001",
                title="T",
                content="C",
                similarity=0.9,
                rerank_score=0.85,
            )
        ]

        _write_execution_log(
            execution_id="EXEC-test",
            graph_type="GAP_DETECTION",
            input_data=input_data,
            query="test query",
            total_latency_ms=500,
            node_latencies={"plan_query": 100},
            final_state={"evidence": evidence, "tokens": None},
            decision=decision,
            status="success",
        )
        mock_client.table.assert_called_with("rag_execution_log")
        row = mock_client.table.return_value.insert.call_args[0][0]
        assert row["execution_id"] == "EXEC-test"
        assert row["graph_type"] == "GAP_DETECTION"
        assert row["status"] == "success"
        assert row["evidence_count"] == 1
        assert row["top_similarity"] == 0.9
        assert row["top_rerank_score"] == 0.85

    @patch("app.rag.core.get_supabase_client")
    def test_handles_db_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.side_effect = (
            RuntimeError("DB error")
        )

        input_data = GapDetectionInput(
            ticket_number="CS-T",
            subject="S",
            description="D",
        )
        # Should not raise
        _write_execution_log(
            execution_id="EXEC-test",
            graph_type="GAP_DETECTION",
            input_data=input_data,
            query="q",
            total_latency_ms=100,
            node_latencies={},
            final_state={},
            decision=None,
            status="error",
            error_message="boom",
        )
        # Verify the insert was actually attempted (exception path was reached)
        mock_client.table.return_value.insert.return_value.execute.assert_called_once()

    @patch("app.rag.core.get_supabase_client")
    def test_extracts_token_counts(self, mock_get_client):
        """When tokens are present in final_state, they are extracted into the row."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from app.rag.core.llm import TokenUsage

        tokens = TokenUsage(input=500, output=200, model="gpt-4o")
        evidence = [
            CorpusHit(
                source_type="KB",
                source_id="KB-001",
                title="T",
                content="C",
                similarity=0.9,
            )
        ]
        input_data = GapDetectionInput(
            ticket_number="CS-T",
            subject="S",
            description="D",
        )
        _write_execution_log(
            execution_id="EXEC-tok",
            graph_type="GAP_DETECTION",
            input_data=input_data,
            query="test",
            total_latency_ms=300,
            node_latencies={},
            final_state={"evidence": evidence, "tokens": tokens},
            decision=None,
            status="success",
        )
        # Verify the insert call includes token counts
        call_args = mock_client.table.return_value.insert.call_args[0][0]
        assert call_args["tokens_input"] == 500
        assert call_args["tokens_output"] == 200