"""Tests for RAG agent node functions with mocked dependencies."""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.core.llm import TokenUsage
from app.rag.models.rag import (
    Citation,
    CorpusHit,
    QueryVariant,
    RagAnswer,
    RagInput,
    RagState,
    RagStatus,
    RetrievalPlan,
    SourceDetail,
)
from app.rag.models.corpus import KnowledgeDecision, KnowledgeDecisionType
from app.rag.agent.nodes import (
    classify_knowledge,
    enrich_sources,
    log_retrieval,
    plan_query,
    rerank,
    retrieve,
    validate,
    write_answer,
)


def _make_state(**overrides) -> RagState:
    """Helper to create a RagState with defaults."""
    defaults = {
        "input": RagInput(question="How do I advance the property date?"),
        "top_k": 10,
    }
    defaults.update(overrides)
    return RagState(**defaults)


def _make_corpus_hit(
    source_type: str = "SCRIPT",
    source_id: str = "SCRIPT-0001",
    similarity: float = 0.85,
) -> CorpusHit:
    """Helper to create a CorpusHit."""
    return CorpusHit(
        source_type=source_type,
        source_id=source_id,
        title=f"Title for {source_id}",
        content=f"Content for {source_id}",
        category="Advance Property Date",
        similarity=similarity,
    )


class TestPlanQuery:
    """Test plan_query node."""

    @patch("app.rag.agent.nodes.LLM")
    def test_returns_retrieval_plan(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.chat.return_value = RetrievalPlan(
            queries=[
                QueryVariant(query="advance property date", rationale="Direct search"),
                QueryVariant(query="date advance script", rationale="Script search"),
            ]
        )
        mock_llm.last_usage = TokenUsage(input=100, output=50, model="gpt-4o")

        state = _make_state()
        result = plan_query(state)

        assert "retrieval_plan" in result
        assert len(result["retrieval_plan"].queries) == 2
        assert result["tokens"].input == 100


class TestRetrieve:
    """Test retrieve node."""

    @patch("app.rag.agent.nodes.get_supabase_client")
    @patch("app.rag.agent.nodes.Embedder")
    def test_deduplicates_by_composite_key(self, mock_embedder_cls, mock_get_client):
        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.embed.return_value = [0.1] * 3072

        # RPC returns same source from two queries
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(
            data=[
                {
                    "source_type": "SCRIPT",
                    "source_id": "SCRIPT-0001",
                    "title": "Fix A",
                    "content": "Content A",
                    "category": "General",
                    "module": "",
                    "tags": "",
                    "similarity": 0.85,
                    "confidence": 0.8,
                    "usage_count": 3,
                },
                {
                    "source_type": "SCRIPT",
                    "source_id": "SCRIPT-0001",
                    "title": "Fix A",
                    "content": "Content A",
                    "category": "General",
                    "module": "",
                    "tags": "",
                    "similarity": 0.90,
                    "confidence": 0.8,
                    "usage_count": 3,
                },
            ]
        )

        plan = RetrievalPlan(
            queries=[
                QueryVariant(query="q1", rationale="r1"),
                QueryVariant(query="q2", rationale="r2"),
            ]
        )
        state = _make_state(retrieval_plan=plan)
        result = retrieve(state)

        # Should deduplicate: one entry, with the higher similarity
        assert len(result["candidates"]) == 1
        assert result["candidates"][0].similarity == 0.90


class TestRerank:
    """Test rerank node."""

    @patch("app.rag.agent.nodes.Reranker")
    def test_adds_rerank_scores(self, mock_reranker_cls):
        mock_reranker = MagicMock()
        mock_reranker_cls.return_value = mock_reranker

        from app.rag.core.reranker import RankedDocument

        mock_reranker.rerank.return_value = [
            RankedDocument(index=1, text="Content B", relevance_score=0.95),
            RankedDocument(index=0, text="Content A", relevance_score=0.80),
        ]

        candidates = [
            _make_corpus_hit(source_id="SCRIPT-0001", similarity=0.85),
            _make_corpus_hit(source_id="SCRIPT-0002", similarity=0.90),
        ]
        state = _make_state(candidates=candidates)
        result = rerank(state)

        assert len(result["evidence"]) == 2
        # rerank_score is blended: raw * (1 - w + w * learning_score)
        # with confidence=0.5, usage=0, no updated_at → learning_score ≈ 0.375
        # blended = 0.95 * (1 - 0.3 + 0.3 * 0.375) = 0.7719
        assert result["evidence"][0].rerank_score == 0.7719
        assert result["evidence"][0].source_id == "SCRIPT-0002"

    def test_empty_candidates(self):
        state = _make_state(candidates=[])
        result = rerank(state)
        assert result["evidence"] == []


class TestEnrichSources:
    """Test enrich_sources node."""

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_enriches_kb_with_lineage(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock kb_lineage query
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_in.execute.return_value = MagicMock(
            data=[
                {
                    "kb_article_id": "KB-SYN-0001",
                    "source_type": "Ticket",
                    "source_id": "CS-38908386",
                },
                {
                    "kb_article_id": "KB-SYN-0001",
                    "source_type": "Conversation",
                    "source_id": "CONV-O2RAK1VRJN",
                },
                {
                    "kb_article_id": "KB-SYN-0001",
                    "source_type": "Script",
                    "source_id": "SCRIPT-0293",
                },
            ]
        )

        evidence = [_make_corpus_hit(source_type="KB", source_id="KB-SYN-0001")]
        state = _make_state(evidence=evidence)
        result = enrich_sources(state)

        assert len(result["source_details"]) == 1
        detail = result["source_details"][0]
        assert detail.lineage_ticket == "CS-38908386"
        assert detail.lineage_conversation == "CONV-O2RAK1VRJN"
        assert detail.lineage_script == "SCRIPT-0293"


class TestValidate:
    """Test validate node."""

    def test_passes_with_evidence_and_citations(self):
        evidence = [_make_corpus_hit()]
        citations = [Citation(source_type="SCRIPT", source_id="SCRIPT-0001")]
        state = _make_state(evidence=evidence, citations=citations)
        result = validate(state)
        assert result["validation_passed"] is True
        assert result["status"] == RagStatus.SUCCESS

    def test_fails_with_no_evidence_first_attempt(self):
        state = _make_state(attempt=0)
        result = validate(state)
        assert result["validation_passed"] is False
        assert result["attempt"] == 1
        assert result["top_k"] == 15  # 10 * 1.5

    def test_fails_permanently_after_retry(self):
        state = _make_state(attempt=1)
        result = validate(state)
        assert result["validation_passed"] is False
        assert result["status"] == RagStatus.INSUFFICIENT_EVIDENCE


class TestClassifyKnowledge:
    """Test classify_knowledge node."""

    def test_no_evidence_returns_new_knowledge(self):
        state = _make_state(evidence=[])
        result = classify_knowledge(state)
        assert RagStatus.SUCCESS in result["status"]

        import json

        decision = json.loads(result["answer"])
        assert decision["decision"] == "NEW_KNOWLEDGE"

    @patch("app.rag.agent.nodes.LLM")
    def test_with_evidence_calls_llm(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.chat.return_value = KnowledgeDecision(
            decision=KnowledgeDecisionType.SAME_KNOWLEDGE,
            reasoning="Resolution matches existing KB article.",
            similarity_score=0.92,
        )
        mock_llm.last_usage = TokenUsage(input=200, output=80, model="gpt-4o")

        evidence = [_make_corpus_hit(similarity=0.92)]
        state = _make_state(evidence=evidence)
        result = classify_knowledge(state)

        mock_llm.chat.assert_called_once()
        assert result["status"] == RagStatus.SUCCESS


class TestLogRetrieval:
    """Test log_retrieval node."""

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_writes_log_entries(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock()

        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock()

        evidence = [
            _make_corpus_hit(source_id="SCRIPT-0001"),
            _make_corpus_hit(source_id="SCRIPT-0002"),
        ]
        state = _make_state(
            input=RagInput(
                question="test", ticket_number="CS-38908386"
            ),
            evidence=evidence,
        )
        result = log_retrieval(state)

        assert result == {}
        mock_table.insert.assert_called_once()
        inserted_entries = mock_table.insert.call_args[0][0]
        assert len(inserted_entries) == 2
        assert inserted_entries[0]["ticket_number"] == "CS-38908386"

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_handles_db_failure_gracefully(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.side_effect = Exception("DB connection lost")

        evidence = [_make_corpus_hit()]
        state = _make_state(evidence=evidence)

        # Should not raise
        result = log_retrieval(state)
        assert result == {}
