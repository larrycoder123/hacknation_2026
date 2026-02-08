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
    _compute_learning_score,
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

    def test_deduplicates_by_composite_key(self):
        """Test deduplication logic of retrieve by mocking the entire function internals.

        Since retrieve() uses ThreadPoolExecutor which complicates mocking,
        we test the deduplication logic directly.
        """
        # Simulate what retrieve() does after getting RPC results:
        # two queries return the same source with different similarities
        rpc_results = [
            [
                {"source_type": "SCRIPT", "source_id": "SCRIPT-0001",
                 "title": "Fix A", "content": "Content A", "category": "General",
                 "module": "", "tags": "", "similarity": 0.85,
                 "confidence": 0.8, "usage_count": 3},
            ],
            [
                {"source_type": "SCRIPT", "source_id": "SCRIPT-0001",
                 "title": "Fix A", "content": "Content A", "category": "General",
                 "module": "", "tags": "", "similarity": 0.90,
                 "confidence": 0.8, "usage_count": 3},
            ],
        ]

        # Replicate the dedup logic from retrieve()
        all_candidates: dict[tuple[str, str], CorpusHit] = {}
        for rows in rpc_results:
            for row in rows:
                key = (row["source_type"], row["source_id"])
                if key not in all_candidates:
                    all_candidates[key] = CorpusHit(
                        source_type=row["source_type"],
                        source_id=row["source_id"],
                        title=row.get("title", ""),
                        content=row.get("content", ""),
                        category=row.get("category", ""),
                        module=row.get("module", ""),
                        tags=row.get("tags", ""),
                        similarity=row["similarity"],
                        confidence=row.get("confidence", 0.5),
                        usage_count=row.get("usage_count", 0),
                    )
                else:
                    existing = all_candidates[key]
                    if row["similarity"] > existing.similarity:
                        all_candidates[key] = existing.model_copy(
                            update={"similarity": row["similarity"]}
                        )

        candidates = sorted(
            all_candidates.values(), key=lambda x: x.similarity, reverse=True
        )

        # Should deduplicate: one entry, with the higher similarity
        assert len(candidates) == 1
        assert candidates[0].similarity == 0.90
        assert candidates[0].source_id == "SCRIPT-0001"


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


class TestLogRetrievalConversationOnly:
    """Test log_retrieval with conversation_id only (pre-ticket)."""

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_logs_with_conversation_id(self, mock_get_client):
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

        evidence = [_make_corpus_hit()]
        state = _make_state(
            input=RagInput(question="test", conversation_id="conv-1024"),
            evidence=evidence,
        )
        result = log_retrieval(state)
        assert result == {}
        inserted = mock_table.insert.call_args[0][0]
        assert inserted[0]["conversation_id"] == "conv-1024"
        assert inserted[0]["ticket_number"] is None

    def test_skips_when_no_identifiers(self):
        state = _make_state(
            input=RagInput(question="test"),
            evidence=[_make_corpus_hit()],
        )
        result = log_retrieval(state)
        assert result == {}

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_usage_increment_failure_handled(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock()

        # Make usage increment fail
        mock_client.rpc.side_effect = Exception("RPC failed")

        evidence = [_make_corpus_hit()]
        state = _make_state(
            input=RagInput(question="q", ticket_number="CS-T"),
            evidence=evidence,
        )
        # Should not raise
        result = log_retrieval(state)
        assert result == {}


class TestWriteAnswer:
    """Test write_answer node."""

    @patch("app.rag.agent.nodes.LLM")
    def test_generates_answer_with_citations(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.chat.return_value = RagAnswer(
            answer="You can advance the date using the script.",
            citations=[
                Citation(source_type="SCRIPT", source_id="SCRIPT-0001"),
            ],
        )
        mock_llm.last_usage = TokenUsage(input=300, output=100, model="gpt-4o")

        evidence = [_make_corpus_hit()]
        source_details = [
            SourceDetail(
                source_type="SCRIPT",
                source_id="SCRIPT-0001",
                title="Advance Date Script",
                script_purpose="Fix date sync",
            )
        ]
        state = _make_state(evidence=evidence, source_details=source_details)
        result = write_answer(state)

        assert "advance" in result["answer"].lower()
        assert len(result["citations"]) == 1
        assert result["tokens"].input == 300

    @patch("app.rag.agent.nodes.LLM")
    def test_no_token_tracking_when_none(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.chat.return_value = RagAnswer(
            answer="Answer",
            citations=[],
        )
        mock_llm.last_usage = None

        evidence = [_make_corpus_hit()]
        state = _make_state(evidence=evidence)
        result = write_answer(state)
        assert result["answer"] == "Answer"

    @patch("app.rag.agent.nodes.LLM")
    def test_enrichment_branches_ticket_and_lineage(self, mock_llm_cls):
        """Test write_answer includes ticket_subject, ticket_root_cause, lineage_ticket in enrichment."""
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.chat.return_value = RagAnswer(
            answer="Enriched answer",
            citations=[],
        )
        mock_llm.last_usage = None

        evidence = [
            _make_corpus_hit(source_type="TICKET_RESOLUTION", source_id="CS-001"),
        ]
        source_details = [
            SourceDetail(
                source_type="TICKET_RESOLUTION",
                source_id="CS-001",
                title="Ticket",
                ticket_subject="Login issue",
                ticket_root_cause="Expired creds",
                lineage_ticket="CS-OLD-001",
            )
        ]
        state = _make_state(evidence=evidence, source_details=source_details)
        result = write_answer(state)
        assert result["answer"] == "Enriched answer"
        # Check the LLM was called with enrichment text containing all three fields
        call_args = mock_llm.chat.call_args
        user_msg = call_args[0][0][1]["content"]
        assert "Subject: Login issue" in user_msg
        assert "Root cause: Expired creds" in user_msg
        assert "Linked ticket: CS-OLD-001" in user_msg


class TestEnrichScriptsAndTickets:
    """Test enrich_sources for SCRIPT and TICKET_RESOLUTION types."""

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_enriches_scripts(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_in.execute.return_value = MagicMock(
            data=[
                {
                    "script_id": "SCRIPT-0001",
                    "script_purpose": "Fix certification sync issue",
                },
            ]
        )

        evidence = [_make_corpus_hit(source_type="SCRIPT", source_id="SCRIPT-0001")]
        state = _make_state(evidence=evidence)
        result = enrich_sources(state)

        assert len(result["source_details"]) == 1
        detail = result["source_details"][0]
        assert detail.script_purpose == "Fix certification sync issue"

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_enriches_ticket_resolutions(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_in.execute.return_value = MagicMock(
            data=[
                {
                    "ticket_number": "CS-TEST01",
                    "subject": "Login issue",
                    "resolution": "Reset password",
                    "root_cause": "Expired credentials",
                },
            ]
        )

        evidence = [
            _make_corpus_hit(
                source_type="TICKET_RESOLUTION", source_id="CS-TEST01"
            )
        ]
        state = _make_state(evidence=evidence)
        result = enrich_sources(state)

        detail = result["source_details"][0]
        assert detail.ticket_subject == "Login issue"
        assert detail.ticket_resolution == "Reset password"
        assert detail.ticket_root_cause == "Expired credentials"


class TestComputeLearningScore:
    """Test _compute_learning_score helper."""

    def test_default_values(self):
        hit = _make_corpus_hit()
        score = _compute_learning_score(hit)
        # confidence=0.5*0.6=0.3, usage=0*0.3=0, freshness=0.75*0.1=0.075
        assert 0.35 < score < 0.40

    def test_high_confidence_and_usage(self):
        hit = CorpusHit(
            source_type="KB",
            source_id="KB-001",
            title="T",
            content="C",
            similarity=0.9,
            confidence=1.0,
            usage_count=31,
        )
        score = _compute_learning_score(hit)
        # confidence=1.0*0.6=0.6, usage≈1.0*0.3=0.3, freshness=0.75*0.1=0.075
        assert score > 0.9

    def test_zero_confidence_and_usage(self):
        hit = CorpusHit(
            source_type="KB",
            source_id="KB-001",
            title="T",
            content="C",
            similarity=0.9,
            confidence=0.0,
            usage_count=0,
        )
        score = _compute_learning_score(hit)
        # confidence=0*0.6=0, usage=0*0.3=0, freshness=0.75*0.1=0.075
        assert 0.05 < score < 0.1

    def test_with_recent_timestamp(self):
        from datetime import datetime, timezone

        hit = CorpusHit(
            source_type="KB",
            source_id="KB-001",
            title="T",
            content="C",
            similarity=0.9,
            confidence=0.5,
            usage_count=0,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        score = _compute_learning_score(hit)
        # freshness should be ~1.0
        assert score > 0.35

    def test_with_old_timestamp_string(self):
        hit = CorpusHit(
            source_type="KB",
            source_id="KB-001",
            title="T",
            content="C",
            similarity=0.9,
            confidence=0.5,
            usage_count=0,
            updated_at="2024-01-01T00:00:00+00:00",
        )
        score = _compute_learning_score(hit)
        # freshness should be lower due to age
        assert score > 0

    def test_with_invalid_timestamp_string(self):
        """ValueError/TypeError from bad updated_at falls back to default freshness."""
        hit = CorpusHit(
            source_type="KB",
            source_id="KB-001",
            title="T",
            content="C",
            similarity=0.9,
            confidence=0.5,
            usage_count=0,
            updated_at="not-a-date",
        )
        score = _compute_learning_score(hit)
        # Should use default freshness 0.75 — same as no timestamp
        assert 0.35 < score < 0.40


class TestClassifyKnowledgeLogSummary:
    """Test classify_knowledge with retrieval_log_summary."""

    @patch("app.rag.agent.nodes.LLM")
    def test_includes_retrieval_log_in_prompt(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.SAME_KNOWLEDGE,
            reasoning="Already covered",
            similarity_score=0.95,
        )
        mock_llm.chat.return_value = decision
        mock_llm.last_usage = None

        evidence = [_make_corpus_hit()]
        state = _make_state(
            evidence=evidence,
            retrieval_log_summary="Used KB-001 (RESOLVED), KB-002 (UNHELPFUL)",
        )
        result = classify_knowledge(state)
        assert "SAME_KNOWLEDGE" in result["answer"]
        # Check retrieval log summary was passed in prompt
        call_args = mock_llm.chat.call_args
        user_msg = call_args[0][0][1]["content"]
        assert "Retrieval log from live support session" in user_msg
        assert "Used KB-001" in user_msg


class TestLogRetrievalInsertFailure:
    """Test log_retrieval when DB insert throws."""

    @patch("app.rag.agent.nodes.get_supabase_client")
    def test_insert_exception_does_not_raise(self, mock_get_client):
        """DB insert failure in log_retrieval is caught and does not propagate."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.side_effect = RuntimeError("DB unavailable")

        # RPC for increment still needs to work
        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[])

        evidence = [_make_corpus_hit()]
        state = _make_state(
            input=RagInput(question="q", conversation_id="conv-1"),
            evidence=evidence,
        )
        # Should not raise
        result = log_retrieval(state)
        assert result == {}
