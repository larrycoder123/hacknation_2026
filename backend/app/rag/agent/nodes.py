"""Node functions for SupportMind RAG agent."""

import logging
import uuid
from datetime import datetime, timezone

from app.rag.core import Embedder, LLM, Reranker, get_supabase_client, settings
from app.rag.models.corpus import KnowledgeDecision, KnowledgeDecisionType
from app.rag.models.rag import (
    Citation,
    CorpusHit,
    RagAnswer,
    RagState,
    RagStatus,
    RetrievalPlan,
    SourceDetail,
)
from app.rag.models.retrieval_log import RetrievalLogEntry, RetrievalOutcome
from app.rag.agent.prompts import (
    CLASSIFY_KNOWLEDGE_SYSTEM,
    PLAN_QUERY_SYSTEM,
    WRITE_ANSWER_SYSTEM,
)

logger = logging.getLogger(__name__)


def plan_query(state: RagState) -> dict:
    """Generate retrieval plan with 2-4 query variants using LLM."""
    llm = LLM()

    messages = [
        {"role": "system", "content": PLAN_QUERY_SYSTEM},
        {"role": "user", "content": f"Question: {state.input.question}"},
    ]

    plan: RetrievalPlan = llm.chat(messages, response_model=RetrievalPlan)

    new_tokens = state.tokens + llm.last_usage if llm.last_usage else state.tokens

    return {"retrieval_plan": plan, "tokens": new_tokens}


def retrieve(state: RagState) -> dict:
    """Embed query variants and call match_corpus RPC, deduplicate by composite key."""
    embedder = Embedder()
    client = get_supabase_client()

    # Composite key: (source_type, source_id)
    all_candidates: dict[tuple[str, str], CorpusHit] = {}

    per_query_k = max(state.top_k, 15)

    # Build RPC params
    source_types_param = None
    if state.input.source_types:
        source_types_param = [st for st in state.input.source_types]

    for variant in state.retrieval_plan.queries:
        query_embedding = embedder.embed(variant.query)

        rpc_params: dict = {
            "query_embedding": query_embedding,
            "p_top_k": per_query_k,
        }
        if source_types_param:
            rpc_params["p_source_types"] = source_types_param
        if state.input.category:
            rpc_params["p_category"] = state.input.category

        result = client.rpc("match_corpus", rpc_params).execute()

        for row in result.data:
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
                    confidence=row.get("confidence", 0.0),
                    usage_count=row.get("usage_count", 0),
                )
            else:
                # Keep highest similarity across query variants
                existing = all_candidates[key]
                if row["similarity"] > existing.similarity:
                    all_candidates[key] = existing.model_copy(
                        update={"similarity": row["similarity"]}
                    )

    # Sort by similarity, take top candidates
    candidates = sorted(
        all_candidates.values(), key=lambda x: x.similarity, reverse=True
    )[: settings.max_retrieval_candidates]

    return {"candidates": candidates}


def rerank(state: RagState) -> dict:
    """Rerank candidates using Cohere to get top evidence."""
    reranker = Reranker()

    if not state.candidates:
        return {"evidence": []}

    documents = [hit.content for hit in state.candidates]

    ranked = reranker.rerank(
        query=state.input.question,
        documents=documents,
        top_k=state.top_k,
    )

    evidence: list[CorpusHit] = []
    for ranked_doc in ranked:
        original = state.candidates[ranked_doc.index]
        evidence.append(
            original.model_copy(update={"rerank_score": ranked_doc.relevance_score})
        )

    return {"evidence": evidence}


def enrich_sources(state: RagState) -> dict:
    """Batch-lookup enrichment data from connected tables (max 3 DB calls)."""
    client = get_supabase_client()
    details: list[SourceDetail] = []

    # Group evidence by source type
    kb_ids: list[str] = []
    script_ids: list[str] = []
    ticket_ids: list[str] = []

    for hit in state.evidence:
        if hit.source_type == "KB":
            kb_ids.append(hit.source_id)
        elif hit.source_type == "SCRIPT":
            script_ids.append(hit.source_id)
        elif hit.source_type == "TICKET_RESOLUTION":
            ticket_ids.append(hit.source_id)

    # Batch lookup: KB -> kb_lineage
    kb_lineage_map: dict[str, dict[str, str]] = {}
    if kb_ids:
        lineage_result = (
            client.table("kb_lineage")
            .select("kb_article_id, source_type, source_id")
            .in_("kb_article_id", kb_ids)
            .execute()
        )
        for row in lineage_result.data:
            kb_id = row["kb_article_id"]
            if kb_id not in kb_lineage_map:
                kb_lineage_map[kb_id] = {}
            if row["source_type"] == "Ticket":
                kb_lineage_map[kb_id]["ticket"] = row["source_id"]
            elif row["source_type"] == "Conversation":
                kb_lineage_map[kb_id]["conversation"] = row["source_id"]
            elif row["source_type"] == "Script":
                kb_lineage_map[kb_id]["script"] = row["source_id"]

    # Batch lookup: SCRIPT -> scripts_master
    script_meta_map: dict[str, dict[str, str]] = {}
    if script_ids:
        script_result = (
            client.table("scripts_master")
            .select("script_id, script_purpose, script_inputs")
            .in_("script_id", script_ids)
            .execute()
        )
        for row in script_result.data:
            script_meta_map[row["script_id"]] = {
                "purpose": row.get("script_purpose", ""),
                "inputs": row.get("script_inputs", ""),
            }

    # Batch lookup: TICKET_RESOLUTION -> tickets
    ticket_meta_map: dict[str, dict[str, str]] = {}
    if ticket_ids:
        ticket_result = (
            client.table("tickets")
            .select("ticket_number, subject, resolution, root_cause")
            .in_("ticket_number", ticket_ids)
            .execute()
        )
        for row in ticket_result.data:
            ticket_meta_map[row["ticket_number"]] = {
                "subject": row.get("subject", ""),
                "resolution": row.get("resolution", ""),
                "root_cause": row.get("root_cause", ""),
            }

    # Build SourceDetail for each evidence item
    for hit in state.evidence:
        detail = SourceDetail(
            source_type=hit.source_type,
            source_id=hit.source_id,
            title=hit.title,
        )

        if hit.source_type == "KB" and hit.source_id in kb_lineage_map:
            lineage = kb_lineage_map[hit.source_id]
            detail = detail.model_copy(
                update={
                    "lineage_ticket": lineage.get("ticket"),
                    "lineage_conversation": lineage.get("conversation"),
                    "lineage_script": lineage.get("script"),
                }
            )
        elif hit.source_type == "SCRIPT" and hit.source_id in script_meta_map:
            meta = script_meta_map[hit.source_id]
            detail = detail.model_copy(
                update={
                    "script_purpose": meta["purpose"],
                    "script_inputs": meta["inputs"],
                }
            )
        elif hit.source_type == "TICKET_RESOLUTION" and hit.source_id in ticket_meta_map:
            meta = ticket_meta_map[hit.source_id]
            detail = detail.model_copy(
                update={
                    "ticket_subject": meta["subject"],
                    "ticket_resolution": meta["resolution"],
                    "ticket_root_cause": meta["root_cause"],
                }
            )

        details.append(detail)

    return {"source_details": details}


def write_answer(state: RagState) -> dict:
    """Generate answer with citations from evidence."""
    llm = LLM()

    # Format evidence with source references
    evidence_text = ""
    hit_map: dict[int, CorpusHit] = {}
    for i, hit in enumerate(state.evidence, start=1):
        evidence_text += (
            f"\n[{i}] ({hit.source_type}: {hit.source_id}, \"{hit.title}\"):\n"
            f"{hit.content}\n"
        )
        hit_map[i] = hit

    # Include enrichment data if available
    enrichment_text = ""
    for detail in state.source_details:
        parts: list[str] = []
        if detail.script_purpose:
            parts.append(f"Purpose: {detail.script_purpose}")
        if detail.script_inputs:
            parts.append(f"Inputs: {detail.script_inputs}")
        if detail.ticket_subject:
            parts.append(f"Subject: {detail.ticket_subject}")
        if detail.ticket_root_cause:
            parts.append(f"Root cause: {detail.ticket_root_cause}")
        if detail.lineage_ticket:
            parts.append(f"Linked ticket: {detail.lineage_ticket}")
        if parts:
            enrichment_text += (
                f"\nEnrichment for {detail.source_type}:{detail.source_id}: "
                + "; ".join(parts)
                + "\n"
            )

    messages = [
        {"role": "system", "content": WRITE_ANSWER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Question: {state.input.question}\n\n"
                f"Evidence:\n{evidence_text}\n"
                f"{enrichment_text}\n"
                "Provide a comprehensive answer with citations."
            ),
        },
    ]

    answer: RagAnswer = llm.chat(messages, response_model=RagAnswer)
    new_tokens = state.tokens + llm.last_usage if llm.last_usage else state.tokens

    return {
        "answer": answer.answer,
        "citations": answer.citations,
        "tokens": new_tokens,
    }


def classify_knowledge(state: RagState) -> dict:
    """Classify whether evidence represents same, contradicting, or new knowledge.

    Used in the gap detection graph. Temperature=0 for deterministic classification.
    """
    # No evidence at all -> NEW_KNOWLEDGE
    if not state.evidence:
        decision = KnowledgeDecision(
            decision=KnowledgeDecisionType.NEW_KNOWLEDGE,
            reasoning="No matching entries found in the corpus.",
            similarity_score=0.0,
        )
        return {"answer": decision.model_dump_json(), "status": RagStatus.SUCCESS}

    best_hit = state.evidence[0]
    best_similarity = best_hit.similarity

    # Below threshold with no close matches -> likely NEW_KNOWLEDGE, but LLM confirms
    llm = LLM()

    evidence_summary = "\n".join(
        f"- [{hit.source_type}: {hit.source_id}] (similarity={hit.similarity:.3f}): "
        f"{hit.content[:300]}"
        for hit in state.evidence[:5]
    )

    # Build optional log context
    log_context = ""
    if state.retrieval_log_summary:
        log_context = (
            f"\nRetrieval log from live support session:\n"
            f"{state.retrieval_log_summary}\n"
        )

    # The ticket info is encoded in the question (constructed in graph.py)
    messages = [
        {"role": "system", "content": CLASSIFY_KNOWLEDGE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Ticket query: {state.input.question}\n\n"
                f"Best similarity score: {best_similarity:.3f}\n"
                f"Similarity threshold: {settings.gap_similarity_threshold}\n\n"
                f"Top matching corpus entries:\n{evidence_summary}\n"
                f"{log_context}\n"
                "Classify this ticket's knowledge."
            ),
        },
    ]

    decision: KnowledgeDecision = llm.chat(
        messages, response_model=KnowledgeDecision, temperature=0.0
    )
    decision = decision.model_copy(
        update={
            "best_match_source_id": best_hit.source_id,
            "similarity_score": best_similarity,
        }
    )

    new_tokens = state.tokens + llm.last_usage if llm.last_usage else state.tokens

    return {
        "answer": decision.model_dump_json(),
        "tokens": new_tokens,
        "status": RagStatus.SUCCESS,
    }


def validate(state: RagState) -> dict:
    """Validate answer quality — check citations and evidence count."""
    errors: list[str] = []

    if len(state.evidence) < 1:
        errors.append("no_evidence")

    if not state.citations:
        errors.append("no_citations")

    if errors:
        if state.attempt < 1:
            return {
                "validation_passed": False,
                "attempt": state.attempt + 1,
                "top_k": int(state.top_k * 1.5),
            }
        return {
            "validation_passed": False,
            "status": RagStatus.INSUFFICIENT_EVIDENCE,
        }

    return {"validation_passed": True, "status": RagStatus.SUCCESS}


def log_retrieval(state: RagState) -> dict:
    """Write retrieval log entries to Supabase for each top hit."""
    client = get_supabase_client()
    ticket_number = state.input.ticket_number

    entries: list[dict] = []
    for i, hit in enumerate(state.evidence[:10]):
        entry = RetrievalLogEntry(
            retrieval_id=f"RET-{uuid.uuid4().hex[:12]}",
            ticket_number=ticket_number,
            attempt_number=state.attempt + 1,
            query_text=state.input.question[:500],
            source_type=hit.source_type,
            source_id=hit.source_id,
            similarity_score=hit.similarity,
            outcome=RetrievalOutcome.PARTIAL,
            created_at=datetime.now(timezone.utc),
        )
        entries.append(entry.model_dump(mode="json"))

    if entries:
        try:
            client.table("retrieval_log").insert(entries).execute()
        except Exception:
            logger.exception(
                "Failed to write retrieval log entries for ticket=%s",
                ticket_number,
            )

    # Increment usage counts for top hits
    for hit in state.evidence[:5]:
        try:
            client.rpc(
                "increment_corpus_usage",
                {"p_source_type": hit.source_type, "p_source_id": hit.source_id},
            ).execute()
        except Exception:
            logger.exception(
                "Failed to increment usage for %s:%s",
                hit.source_type,
                hit.source_id,
            )

    return {}
