"""LangGraph workflows for SupportMind RAG.

Two graphs:
1. QA Graph — customer support question answering
2. Gap Detection Graph — learning loop knowledge classification
"""

import logging

from langgraph.graph import END, StateGraph

from app.rag.models.corpus import (
    GapDetectionInput,
    GapDetectionResult,
    KnowledgeDecision,
)
from app.rag.models.rag import (
    CorpusSourceType,
    RagInput,
    RagResult,
    RagState,
    RagStatus,
)
from app.rag.agent import nodes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# QA Graph
# ---------------------------------------------------------------------------


def should_retry_or_finish(state: RagState) -> str:
    """Determine whether to retry retrieval or finish."""
    if state.validation_passed:
        return "finish"
    if state.attempt < 1 and state.status != RagStatus.INSUFFICIENT_EVIDENCE:
        return "retry"
    return "finish"


def create_rag_graph() -> StateGraph:
    """Build the QA RAG workflow graph.

    Flow: plan_query -> retrieve -> rerank -> enrich_sources -> write_answer
          -> validate -> [retry -> retrieve | log_retrieval -> END]
    """
    workflow = StateGraph(RagState)

    workflow.add_node("plan_query", nodes.plan_query)
    workflow.add_node("retrieve", nodes.retrieve)
    workflow.add_node("rerank", nodes.rerank)
    workflow.add_node("enrich_sources", nodes.enrich_sources)
    workflow.add_node("write_answer", nodes.write_answer)
    workflow.add_node("validate", nodes.validate)
    workflow.add_node("log_retrieval", nodes.log_retrieval)

    workflow.set_entry_point("plan_query")

    workflow.add_edge("plan_query", "retrieve")
    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "enrich_sources")
    workflow.add_edge("enrich_sources", "write_answer")
    workflow.add_edge("write_answer", "validate")

    workflow.add_conditional_edges(
        "validate",
        should_retry_or_finish,
        {"retry": "retrieve", "finish": "log_retrieval"},
    )
    workflow.add_edge("log_retrieval", END)

    return workflow


def run_rag(
    question: str,
    category: str | None = None,
    source_types: list[CorpusSourceType] | None = None,
    top_k: int = 10,
    ticket_number: str | None = None,
    conversation_id: str | None = None,
) -> RagResult:
    """Run the QA RAG agent to answer a question.

    Args:
        question: User question
        category: Optional category filter
        source_types: Optional source type filter
        top_k: Number of evidence items to use
        ticket_number: Optional ticket number for retrieval logging
        conversation_id: Optional conversation ID for pre-ticket logging

    Returns:
        RagResult with answer, citations, and top hits
    """
    workflow = create_rag_graph()
    app = workflow.compile()

    input_data = RagInput(
        question=question,
        category=category,
        source_types=source_types,
        top_k=top_k,
        ticket_number=ticket_number,
        conversation_id=conversation_id,
    )

    initial_state = RagState(input=input_data, top_k=top_k)

    try:
        final_state = app.invoke(initial_state)

        retrieval_queries: list[str] = []
        plan = final_state.get("retrieval_plan")
        if plan:
            retrieval_queries = [q.query for q in plan.queries]

        evidence = final_state.get("evidence", [])
        citations = final_state.get("citations", [])

        return RagResult(
            question=question,
            answer=final_state.get("answer", "Unable to generate answer."),
            citations=citations,
            status=final_state.get("status", RagStatus.SUCCESS),
            evidence_count=len(evidence),
            retrieval_queries=retrieval_queries,
            top_hits=evidence,
        )

    except Exception as e:
        logger.exception("RAG workflow failed for question: %s", question[:100])
        return RagResult(
            question=question,
            answer=f"Error processing question: {e!s}",
            citations=[],
            status=RagStatus.ERROR,
            evidence_count=0,
            retrieval_queries=[],
        )


# ---------------------------------------------------------------------------
# Gap Detection Graph
# ---------------------------------------------------------------------------


def create_gap_detection_graph() -> StateGraph:
    """Build the gap detection workflow graph.

    Flow: plan_query -> retrieve -> rerank -> enrich_sources
          -> classify_knowledge -> log_retrieval -> END
    """
    workflow = StateGraph(RagState)

    workflow.add_node("plan_query", nodes.plan_query)
    workflow.add_node("retrieve", nodes.retrieve)
    workflow.add_node("rerank", nodes.rerank)
    workflow.add_node("enrich_sources", nodes.enrich_sources)
    workflow.add_node("classify_knowledge", nodes.classify_knowledge)
    workflow.add_node("log_retrieval", nodes.log_retrieval)

    workflow.set_entry_point("plan_query")

    workflow.add_edge("plan_query", "retrieve")
    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "enrich_sources")
    workflow.add_edge("enrich_sources", "classify_knowledge")
    workflow.add_edge("classify_knowledge", "log_retrieval")
    workflow.add_edge("log_retrieval", END)

    return workflow


def run_gap_detection(input_data: GapDetectionInput) -> GapDetectionResult:
    """Run gap detection to classify a resolved ticket's knowledge.

    Constructs a query from ticket fields, searches the corpus, and classifies
    as SAME_KNOWLEDGE, CONTRADICTS, or NEW_KNOWLEDGE.

    Args:
        input_data: Resolved ticket details

    Returns:
        GapDetectionResult with decision, retrieved entries, and enriched sources
    """
    # Construct query from ticket fields
    parts: list[str] = []
    if input_data.subject:
        parts.append(input_data.subject)
    if input_data.root_cause:
        parts.append(input_data.root_cause)
    if input_data.category:
        parts.append(input_data.category)
    if input_data.resolution:
        parts.append(f"Resolution: {input_data.resolution[:200]}")
    query = ". ".join(parts) if parts else input_data.description[:300]

    workflow = create_gap_detection_graph()
    app = workflow.compile()

    rag_input = RagInput(
        question=query,
        category=input_data.category or None,
        top_k=10,
        ticket_number=input_data.ticket_number,
    )

    initial_state = RagState(
        input=rag_input,
        top_k=10,
        retrieval_log_summary=input_data.retrieval_log_summary,
    )

    try:
        final_state = app.invoke(initial_state)

        # Parse the decision from the answer field (stored as JSON by classify_knowledge)
        answer_json = final_state.get("answer", "{}")
        decision = KnowledgeDecision.model_validate_json(answer_json)

        return GapDetectionResult(
            decision=decision,
            retrieved_entries=final_state.get("evidence", []),
            enriched_sources=final_state.get("source_details", []),
            query_used=query,
        )

    except Exception as e:
        logger.exception(
            "Gap detection failed for ticket: %s", input_data.ticket_number
        )
        from app.rag.models.corpus import KnowledgeDecisionType

        return GapDetectionResult(
            decision=KnowledgeDecision(
                decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
                reasoning=f"Gap detection failed: {e!s}",
                similarity_score=0.0,
            ),
            query_used=query,
        )
