"""LangGraph workflows for SupportMind RAG.

Two graphs:
1. QA Graph — customer support question answering
2. Gap Detection Graph — learning loop knowledge classification
"""

import logging
import time
import uuid

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
# Gap Detection Graph (with execution logging)
# ---------------------------------------------------------------------------


def _timed_node(node_fn, node_latencies: dict):
    """Wrap a node function to record its execution time."""
    name = node_fn.__name__

    def wrapper(state):
        start = time.perf_counter()
        result = node_fn(state)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        node_latencies[name] = elapsed_ms
        return result

    wrapper.__name__ = name
    return wrapper


def create_gap_detection_graph(node_latencies: dict) -> StateGraph:
    """Build the gap detection workflow graph with per-node timing.

    Flow: plan_query -> retrieve -> rerank -> enrich_sources
          -> classify_knowledge -> log_retrieval -> END
    """
    workflow = StateGraph(RagState)

    workflow.add_node("plan_query", _timed_node(nodes.plan_query, node_latencies))
    workflow.add_node("retrieve", _timed_node(nodes.retrieve, node_latencies))
    workflow.add_node("rerank", _timed_node(nodes.rerank, node_latencies))
    workflow.add_node("enrich_sources", _timed_node(nodes.enrich_sources, node_latencies))
    workflow.add_node("classify_knowledge", _timed_node(nodes.classify_knowledge, node_latencies))
    workflow.add_node("log_retrieval", _timed_node(nodes.log_retrieval, node_latencies))

    workflow.set_entry_point("plan_query")

    workflow.add_edge("plan_query", "retrieve")
    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "enrich_sources")
    workflow.add_edge("enrich_sources", "classify_knowledge")
    workflow.add_edge("classify_knowledge", "log_retrieval")
    workflow.add_edge("log_retrieval", END)

    return workflow


def _write_execution_log(
    execution_id: str,
    graph_type: str,
    input_data: GapDetectionInput,
    query: str,
    total_latency_ms: int,
    node_latencies: dict,
    final_state: dict,
    decision: KnowledgeDecision | None,
    status: str,
    error_message: str | None = None,
) -> None:
    """Write a row to rag_execution_log after pipeline completion."""
    try:
        from app.rag.core import get_supabase_client

        client = get_supabase_client()

        evidence = final_state.get("evidence", [])
        tokens = final_state.get("tokens")

        tokens_input = 0
        tokens_output = 0
        if tokens:
            tokens_input = getattr(tokens, "input_tokens", 0) or 0
            tokens_output = getattr(tokens, "output_tokens", 0) or 0

        top_similarity = evidence[0].similarity if evidence else None
        top_rerank = evidence[0].rerank_score if evidence else None

        row = {
            "execution_id": execution_id,
            "graph_type": graph_type,
            "conversation_id": input_data.conversation_id or None,
            "ticket_number": input_data.ticket_number or None,
            "query": query[:1000],
            "total_latency_ms": total_latency_ms,
            "node_latencies": node_latencies,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "evidence_count": len(evidence),
            "top_similarity": round(top_similarity, 4) if top_similarity else None,
            "top_rerank_score": round(top_rerank, 4) if top_rerank else None,
            "classification": decision.decision if decision else None,
            "status": status,
            "error_message": error_message,
        }

        client.table("rag_execution_log").insert(row).execute()
        logger.info(
            "Execution log: %s ticket=%s latency=%dms tokens=%d+%d classification=%s",
            execution_id,
            input_data.ticket_number,
            total_latency_ms,
            tokens_input,
            tokens_output,
            decision.decision if decision else "N/A",
        )
    except Exception:
        logger.exception("Failed to write execution log %s", execution_id)


def run_gap_detection(input_data: GapDetectionInput) -> GapDetectionResult:
    """Run gap detection to classify a resolved ticket's knowledge.

    Constructs a query from ticket fields, searches the corpus, and classifies
    as SAME_KNOWLEDGE, CONTRADICTS, or NEW_KNOWLEDGE. Logs pipeline execution
    metrics to rag_execution_log.

    Args:
        input_data: Resolved ticket details

    Returns:
        GapDetectionResult with decision, retrieved entries, and enriched sources
    """
    execution_id = f"EXEC-{uuid.uuid4().hex[:12]}"
    node_latencies: dict[str, int] = {}
    pipeline_start = time.perf_counter()

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

    workflow = create_gap_detection_graph(node_latencies)
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
        execution_id=execution_id,
    )

    try:
        final_state = app.invoke(initial_state)
        total_ms = int((time.perf_counter() - pipeline_start) * 1000)

        # Parse the decision from the answer field (stored as JSON by classify_knowledge)
        answer_json = final_state.get("answer", "{}")
        decision = KnowledgeDecision.model_validate_json(answer_json)

        _write_execution_log(
            execution_id=execution_id,
            graph_type="GAP_DETECTION",
            input_data=input_data,
            query=query,
            total_latency_ms=total_ms,
            node_latencies=node_latencies,
            final_state=final_state,
            decision=decision,
            status="success",
        )

        return GapDetectionResult(
            decision=decision,
            retrieved_entries=final_state.get("evidence", []),
            enriched_sources=final_state.get("source_details", []),
            query_used=query,
        )

    except Exception as e:
        total_ms = int((time.perf_counter() - pipeline_start) * 1000)
        logger.exception(
            "Gap detection failed for ticket: %s", input_data.ticket_number
        )
        from app.rag.models.corpus import KnowledgeDecisionType

        _write_execution_log(
            execution_id=execution_id,
            graph_type="GAP_DETECTION",
            input_data=input_data,
            query=query,
            total_latency_ms=total_ms,
            node_latencies=node_latencies,
            final_state={},
            decision=None,
            status="error",
            error_message=str(e)[:500],
        )

        return GapDetectionResult(
            decision=KnowledgeDecision(
                decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
                reasoning=f"Gap detection failed: {e!s}",
                similarity_score=0.0,
            ),
            query_used=query,
        )
