"""Self-learning pipeline: post-conversation confidence updates, gap detection, and KB drafting."""

import uuid
from datetime import UTC, datetime
from typing import cast

from app.core.config import get_settings
from app.core.llm import generate_structured_output
from app.db.client import get_supabase
from app.schemas.learning import (
    ConfidenceUpdate,
    KBDraftFromGap,
    KBLineageRecord,
    LearningEventRecord,
    RetrievalLogEntry,
    ReviewDecision,
    SelfLearningResult,
)
from app.services.embedding_service import generate_embedding

# ── Public API ────────────────────────────────────────────────────────


async def run_post_conversation_learning(ticket_number: str) -> SelfLearningResult:
    """Run the full self-learning pipeline for a closed ticket.

    Steps:
        1. Fetch retrieval_log entries for the ticket.
        2. Update confidence on retrieval_corpus per outcome.
        3. Detect knowledge gaps (all attempts UNHELPFUL).
        4. If gap: draft KB article, create learning_event, lineage, embed.

    Args:
        ticket_number: The ticket to process.

    Returns:
        SelfLearningResult with all outcomes.
    """
    logs = _fetch_retrieval_logs(ticket_number)

    if not logs:
        return SelfLearningResult(
            ticket_number=ticket_number,
            retrieval_logs_processed=0,
            confidence_updates=[],
            gap_detected=False,
        )

    confidence_updates = _update_confidence_scores(logs)

    gap_detected = _is_knowledge_gap(logs)

    learning_event_id: str | None = None
    drafted_kb_id: str | None = None

    if gap_detected:
        learning_event_id, drafted_kb_id = await _handle_gap(ticket_number, logs)

    return SelfLearningResult(
        ticket_number=ticket_number,
        retrieval_logs_processed=len(logs),
        confidence_updates=confidence_updates,
        gap_detected=gap_detected,
        learning_event_id=learning_event_id,
        drafted_kb_article_id=drafted_kb_id,
    )


async def review_learning_event(event_id: str, decision: ReviewDecision) -> LearningEventRecord:
    """Approve or reject a learning event's drafted KB article.

    Approved: set KB status='Active', update learning_event.
    Rejected: set KB status='Archived', remove from retrieval_corpus, update learning_event.

    Args:
        event_id: The learning_events.event_id.
        decision: Approved or Rejected with reviewer info.

    Returns:
        Updated LearningEventRecord.
    """
    sb = get_supabase()

    event_row = sb.table("learning_events").select("*").eq("event_id", event_id).single().execute()
    event_data = cast(dict[str, str | None], event_row.data)
    kb_article_id = event_data["proposed_kb_article_id"]

    now = datetime.now(UTC).isoformat()

    sb.table("learning_events").update(
        {
            "final_status": decision.decision,
            "reviewer_role": decision.reviewer_role,
            "event_timestamp": now,
        }
    ).eq("event_id", event_id).execute()

    if decision.decision == "Approved":
        sb.table("knowledge_articles").update(
            {
                "status": "Active",
                "updated_at": now,
            }
        ).eq("kb_article_id", kb_article_id).execute()
    else:
        sb.table("knowledge_articles").update(
            {
                "status": "Archived",
                "updated_at": now,
            }
        ).eq("kb_article_id", kb_article_id).execute()

        sb.table("retrieval_corpus").delete().eq("source_type", "KB").eq(
            "source_id", kb_article_id
        ).execute()

    updated = sb.table("learning_events").select("*").eq("event_id", event_id).single().execute()
    return LearningEventRecord(**cast(dict[str, str | None], updated.data))  # type: ignore[arg-type]


# ── Internal helpers ──────────────────────────────────────────────────


def _fetch_retrieval_logs(ticket_number: str) -> list[RetrievalLogEntry]:
    """Fetch all retrieval_log entries for a ticket, ordered by attempt."""
    sb = get_supabase()
    result = (
        sb.table("retrieval_log")
        .select("*")
        .eq("ticket_number", ticket_number)
        .order("attempt_number")
        .execute()
    )
    rows = cast(list[dict[str, object]], result.data)
    return [RetrievalLogEntry(**row) for row in rows]  # type: ignore[arg-type]


def _update_confidence_scores(logs: list[RetrievalLogEntry]) -> list[ConfidenceUpdate]:
    """Update retrieval_corpus confidence for each log entry with a corpus match."""
    settings = get_settings()
    sb = get_supabase()
    updates: list[ConfidenceUpdate] = []

    delta_map: dict[str, tuple[float, bool]] = {
        "RESOLVED": (settings.confidence_delta_resolved, True),
        "PARTIAL": (settings.confidence_delta_partial, False),
        "UNHELPFUL": (settings.confidence_delta_unhelpful, False),
    }

    for log in logs:
        if log.source_type is None or log.source_id is None or log.outcome is None:
            continue
        if log.outcome not in delta_map:
            continue

        delta, increment_usage = delta_map[log.outcome]

        rpc_result = sb.rpc(
            "update_corpus_confidence",
            {
                "p_source_type": log.source_type,
                "p_source_id": log.source_id,
                "p_delta": delta,
                "p_increment_usage": increment_usage,
            },
        ).execute()

        if rpc_result.data:
            raw = rpc_result.data
            row = cast(
                dict[str, float | int],
                raw[0] if isinstance(raw, list) else raw,
            )
            updates.append(
                ConfidenceUpdate(
                    source_type=log.source_type,
                    source_id=log.source_id,
                    delta=delta,
                    new_confidence=float(row["new_confidence"]),
                    new_usage_count=int(row["new_usage_count"]),
                )
            )

    return updates


def _is_knowledge_gap(logs: list[RetrievalLogEntry]) -> bool:
    """A gap exists when ALL retrieval attempts have outcome=UNHELPFUL."""
    outcomes = [log.outcome for log in logs if log.outcome is not None]
    if not outcomes:
        return False
    return all(o == "UNHELPFUL" for o in outcomes)


async def _handle_gap(
    ticket_number: str,
    logs: list[RetrievalLogEntry],
) -> tuple[str, str]:
    """Draft a KB article, save it, create lineage + learning_event, and embed.

    Returns:
        (learning_event_id, kb_article_id)
    """
    sb = get_supabase()

    ticket_row = (
        sb.table("tickets").select("*").eq("ticket_number", ticket_number).single().execute()
    )
    ticket_data = cast(dict[str, str | None], ticket_row.data)

    conv_row = (
        sb.table("conversations").select("*").eq("ticket_number", ticket_number).single().execute()
    )
    conv_data = cast(dict[str, str | None], conv_row.data)

    draft = await _draft_kb_article(ticket_data, conv_data, logs)

    kb_article_id = f"KB-SYN-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(UTC).isoformat()

    sb.table("knowledge_articles").insert(
        {
            "kb_article_id": kb_article_id,
            "title": draft.title,
            "body": draft.body,
            "tags": draft.tags,
            "module": draft.module,
            "category": draft.category,
            "created_at": now,
            "updated_at": now,
            "status": "Draft",
            "source_type": "SYNTH_FROM_TICKET",
        }
    ).execute()

    event_id = f"LE-{uuid.uuid4().hex[:12]}"
    gap_description = _build_gap_description(logs)

    sb.table("learning_events").insert(
        {
            "event_id": event_id,
            "trigger_ticket_number": ticket_number,
            "detected_gap": gap_description,
            "proposed_kb_article_id": kb_article_id,
            "draft_summary": draft.title,
            "final_status": None,
            "event_timestamp": now,
        }
    ).execute()

    _create_lineage_records(kb_article_id, ticket_number, ticket_data, conv_data, now)

    _embed_kb_article(kb_article_id, draft)

    return event_id, kb_article_id


async def _draft_kb_article(
    ticket: dict[str, str | None],
    conversation: dict[str, str | None],
    logs: list[RetrievalLogEntry],
) -> KBDraftFromGap:
    """Use the LLM to draft a KB article from ticket context."""
    queries = "\n".join(f"  - {log.query_text}" for log in logs)

    prompt = f"""A support ticket was resolved but NO existing knowledge base article could help.
The agent had to solve the issue from scratch. Draft a KB article capturing this knowledge.

TICKET NUMBER: {ticket.get("ticket_number", "N/A")}
SUBJECT: {ticket.get("subject", "N/A")}
DESCRIPTION: {ticket.get("description", "N/A")}
ROOT CAUSE: {ticket.get("root_cause", "N/A")}
RESOLUTION: {ticket.get("resolution", "N/A")}
MODULE: {ticket.get("module", "N/A")}
CATEGORY: {conversation.get("category", "N/A")}
PRODUCT: {conversation.get("product", "N/A")}

AGENT TRANSCRIPT (summary):
{(conversation.get("transcript") or "No transcript available.")[:3000]}

FAILED SEARCH QUERIES (all returned unhelpful results):
{queries}

Create a comprehensive KB article that would have helped resolve this ticket.
Include the problem description, root cause analysis, and step-by-step resolution."""

    system_prompt = """You are a technical writer creating knowledge base articles from resolved
support tickets where no existing KB article could help. Your article must be:
- Clear and actionable for future support agents
- Searchable with relevant tags
- Structured with problem description, root cause, and resolution steps"""

    return await generate_structured_output(
        prompt=prompt,
        output_schema=KBDraftFromGap,
        system_prompt=system_prompt,
        temperature=0,
    )


def _build_gap_description(logs: list[RetrievalLogEntry]) -> str:
    """Summarize what queries failed for the gap detection record."""
    queries = [log.query_text for log in logs]
    joined = "; ".join(queries[:5])
    return f"All {len(queries)} retrieval attempts returned UNHELPFUL. Queries: {joined}"


def _create_lineage_records(
    kb_article_id: str,
    ticket_number: str,
    ticket_data: dict[str, str | None],
    conversation: dict[str, str | None],
    timestamp: str,
) -> None:
    """Create 3 kb_lineage records per rule 9."""
    sb = get_supabase()
    conversation_id = conversation.get("conversation_id", ticket_number)
    script_id = ticket_data.get("script_id")

    ts = datetime.fromisoformat(timestamp)

    records = [
        KBLineageRecord(
            kb_article_id=kb_article_id,
            source_type="Ticket",
            source_id=ticket_number,
            relationship="CREATED_FROM",
            evidence_snippet=f"KB drafted from gap detected in ticket {ticket_number}",
            event_timestamp=ts,
        ),
        KBLineageRecord(
            kb_article_id=kb_article_id,
            source_type="Conversation",
            source_id=conversation_id or ticket_number,
            relationship="CREATED_FROM",
            evidence_snippet="Conversation transcript used as source context",
            event_timestamp=ts,
        ),
        KBLineageRecord(
            kb_article_id=kb_article_id,
            source_type="Script",
            source_id=script_id or ticket_number,
            relationship="REFERENCES" if script_id is None else "CREATED_FROM",
            evidence_snippet="No script associated with ticket"
            if script_id is None
            else f"Linked script {script_id} from resolved ticket",
            event_timestamp=ts,
        ),
    ]

    sb.table("kb_lineage").insert([r.model_dump(mode="json") for r in records]).execute()


def _embed_kb_article(kb_article_id: str, draft: KBDraftFromGap) -> None:
    """Embed the drafted KB article into retrieval_corpus."""
    sb = get_supabase()
    embedding = generate_embedding(draft.body)

    sb.table("retrieval_corpus").insert(
        {
            "source_type": "KB",
            "source_id": kb_article_id,
            "title": draft.title,
            "content": draft.body,
            "category": draft.category,
            "module": draft.module,
            "tags": draft.tags,
            "embedding": embedding,
            "confidence": 0.5,
            "usage_count": 0,
        }
    ).execute()
