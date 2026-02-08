"""Self-learning pipeline: post-conversation confidence updates, gap detection, and KB drafting.

Two-stage pipeline:
    Stage 1 — Score retrieval logs: update confidence on corpus entries based on outcomes.
    Stage 2 — Fresh gap detection: run RAG-powered gap detection with the ticket's resolution
              context + retrieval log summary. Classifies as SAME_KNOWLEDGE, CONTRADICTS,
              or NEW_KNOWLEDGE and acts accordingly.
"""

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import cast

from app.core.config import get_settings
from app.core.llm import generate_structured_output
from app.db.client import get_supabase
from app.rag.agent.graph import run_gap_detection
from app.rag.core import Embedder
from app.rag.models.corpus import GapDetectionInput, GapDetectionResult, KnowledgeDecisionType
from app.schemas.learning import (
    ConfidenceUpdate,
    KBDraftFromGap,
    KBLineageRecord,
    LearningEventRecord,
    RetrievalLogEntry,
    ReviewDecision,
    SelfLearningResult,
)

logger = logging.getLogger(__name__)

# ── Public API ────────────────────────────────────────────────────────


async def run_post_conversation_learning(
    ticket_number: str,
    resolved: bool = True,
    conversation_id: str | None = None,
) -> SelfLearningResult:
    """Run the full self-learning pipeline for a closed ticket.

    Stage 0: Link retrieval_log entries from conversation_id to ticket_number,
             then bulk-set outcomes based on resolution status.
    Stage 1: Fetch retrieval_log entries, update confidence scores on corpus.
    Stage 2: Run fresh RAG gap detection against the ticket's resolution.
    Stage 3: Act on classification (SAME_KNOWLEDGE / CONTRADICTS / NEW_KNOWLEDGE).

    Args:
        ticket_number: The ticket to process.
        resolved: Whether the conversation was resolved successfully.
                  True → all retrieval_log outcomes set to RESOLVED.
                  False → all set to UNHELPFUL.
        conversation_id: Original conversation ID, used to link pre-ticket
                        retrieval logs to the now-created ticket.

    Returns:
        SelfLearningResult with all outcomes.
    """
    # ── Stage 0: Link logs & set outcomes ─────────────────────────
    if conversation_id:
        _link_logs_to_ticket(conversation_id, ticket_number)
    _set_bulk_outcomes(ticket_number, resolved)

    # ── Stage 1: Score retrieval logs ─────────────────────────────
    logs = _fetch_retrieval_logs(ticket_number)
    confidence_updates = _update_confidence_scores(logs) if logs else []
    log_summary = _build_log_summary(logs)

    # ── Stage 2: Fresh gap detection via RAG ──────────────────────
    ticket_data, conv_data = _fetch_ticket_and_conversation(ticket_number)

    gap_input = GapDetectionInput(
        ticket_number=ticket_number,
        conversation_id=str(conv_data.get("conversation_id", "")),
        category=str(ticket_data.get("category", "")),
        subject=str(ticket_data.get("subject", "")),
        description=str(ticket_data.get("description", "")),
        resolution=str(ticket_data.get("resolution", "")),
        root_cause=str(ticket_data.get("root_cause", "")),
        transcript=str(conv_data.get("transcript", ""))[:3000],
        script_id=str(ticket_data.get("script_id", "")),
        retrieval_log_summary=log_summary,
    )

    gap_result = run_gap_detection(gap_input)
    classification = gap_result.decision.decision

    # ── Stage 3: Act on classification ────────────────────────────
    learning_event_id: str | None = None
    drafted_kb_id: str | None = None
    matched_kb_id: str | None = gap_result.decision.best_match_source_id
    match_similarity: float | None = gap_result.decision.similarity_score or None

    if classification == KnowledgeDecisionType.SAME_KNOWLEDGE:
        learning_event_id = _handle_same_knowledge(
            ticket_number, gap_result, ticket_data, conv_data
        )

    elif classification == KnowledgeDecisionType.CONTRADICTS:
        learning_event_id, drafted_kb_id = await _handle_contradiction(
            ticket_number, gap_result, ticket_data, conv_data, logs
        )

    elif classification == KnowledgeDecisionType.NEW_KNOWLEDGE:
        learning_event_id, drafted_kb_id = await _handle_new_knowledge(
            ticket_number, ticket_data, conv_data, logs
        )

    return SelfLearningResult(
        ticket_number=ticket_number,
        retrieval_logs_processed=len(logs),
        confidence_updates=confidence_updates,
        gap_classification=classification,
        matched_kb_article_id=matched_kb_id,
        match_similarity=match_similarity,
        learning_event_id=learning_event_id,
        drafted_kb_article_id=drafted_kb_id,
    )


async def review_learning_event(event_id: str, decision: ReviewDecision) -> LearningEventRecord:
    """Approve or reject a learning event's drafted KB article.

    For GAP events:
        Approved: set KB status='Active', update learning_event.
        Rejected: set KB status='Archived', remove from retrieval_corpus.

    For CONTRADICTION events:
        Approved: replace old KB content with new draft, update embedding.
        Rejected: keep existing KB, archive draft, remove draft from corpus.

    Args:
        event_id: The learning_events.event_id.
        decision: Approved or Rejected with reviewer info.

    Returns:
        Updated LearningEventRecord.
    """
    sb = get_supabase()

    event_row = sb.table("learning_events").select("*").eq("event_id", event_id).single().execute()
    event_data = cast(dict[str, str | None], event_row.data)
    kb_article_id = event_data.get("proposed_kb_article_id")
    event_type = event_data.get("event_type", "GAP")
    flagged_kb_id = event_data.get("flagged_kb_article_id")

    now = datetime.now(UTC).isoformat()

    sb.table("learning_events").update(
        {
            "final_status": decision.decision,
            "reviewer_role": decision.reviewer_role,
            "event_timestamp": now,
        }
    ).eq("event_id", event_id).execute()

    if decision.decision == "Approved":
        if event_type == "CONTRADICTION" and flagged_kb_id and kb_article_id:
            # Replace old KB with the new draft content
            _apply_contradiction_approval(flagged_kb_id, kb_article_id, now)
        elif kb_article_id:
            # GAP: activate the drafted article
            sb.table("knowledge_articles").update(
                {"status": "Active", "updated_at": now}
            ).eq("kb_article_id", kb_article_id).execute()
    else:
        # Rejected: archive draft and remove from corpus
        if kb_article_id:
            sb.table("knowledge_articles").update(
                {"status": "Archived", "updated_at": now}
            ).eq("kb_article_id", kb_article_id).execute()

            sb.table("retrieval_corpus").delete().eq("source_type", "KB").eq(
                "source_id", kb_article_id
            ).execute()

    updated = sb.table("learning_events").select("*").eq("event_id", event_id).single().execute()
    return LearningEventRecord(**cast(dict[str, str | None], updated.data))  # type: ignore[arg-type]


# ── Stage 1 helpers: Log scoring ─────────────────────────────────────


def _link_logs_to_ticket(conversation_id: str, ticket_number: str) -> None:
    """Link pre-ticket retrieval_log entries to the now-created ticket.

    During live support, retrieval logs are written with conversation_id only
    (no ticket_number). Once the ticket is created at close, this function
    stamps the ticket_number onto those logs so Stage 1 can find them.
    """
    sb = get_supabase()
    try:
        sb.table("retrieval_log").update(
            {"ticket_number": ticket_number}
        ).eq("conversation_id", conversation_id).is_("ticket_number", "null").execute()
        logger.info(
            "Linked retrieval_log entries from conversation=%s to ticket=%s",
            conversation_id,
            ticket_number,
        )
    except Exception:
        logger.exception(
            "Failed to link retrieval logs for conversation=%s", conversation_id
        )


def _set_bulk_outcomes(ticket_number: str, resolved: bool) -> None:
    """Bulk-set outcomes on all retrieval_log entries for a ticket.

    Called when the conversation closes. If the agent resolved the issue,
    all RAG attempts are marked RESOLVED (they contributed to the resolution).
    If not resolved, all are marked UNHELPFUL.
    """
    sb = get_supabase()
    outcome = "RESOLVED" if resolved else "UNHELPFUL"

    try:
        sb.table("retrieval_log").update(
            {"outcome": outcome}
        ).eq("ticket_number", ticket_number).is_("outcome", "null").execute()
        logger.info(
            "Bulk-set %s outcome on retrieval_log for ticket=%s",
            outcome,
            ticket_number,
        )
    except Exception:
        logger.exception("Failed to bulk-set outcomes for ticket %s", ticket_number)


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


def _build_log_summary(logs: list[RetrievalLogEntry]) -> str | None:
    """Build a human-readable summary of retrieval log outcomes for the LLM classifier."""
    if not logs:
        return None

    outcomes = [log.outcome for log in logs if log.outcome is not None]
    if not outcomes:
        return f"{len(logs)} retrieval attempts, no outcomes recorded yet."

    counts = Counter(outcomes)
    parts = [f"{count} {outcome}" for outcome, count in counts.items()]
    queries = [log.query_text for log in logs[:5]]
    query_list = "; ".join(queries)

    return (
        f"{len(logs)} retrieval attempts during live support: {', '.join(parts)}. "
        f"Queries: {query_list}"
    )


# ── Stage 2 helpers: Data fetching ───────────────────────────────────


def _fetch_ticket_and_conversation(
    ticket_number: str,
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    """Fetch ticket and conversation data from Supabase.

    Uses maybe_single() to gracefully handle missing rows (returns empty
    dict instead of raising PGRST116).
    """
    sb = get_supabase()

    ticket_row = (
        sb.table("tickets").select("*").eq("ticket_number", ticket_number).maybe_single().execute()
    )
    ticket_data = cast(dict[str, str | None], ticket_row.data or {})

    conv_row = (
        sb.table("conversations").select("*").eq("ticket_number", ticket_number).maybe_single().execute()
    )
    conv_data = cast(dict[str, str | None], conv_row.data or {})

    return ticket_data, conv_data


# ── Stage 3 handlers: Act on classification ──────────────────────────


def _handle_same_knowledge(
    ticket_number: str,
    gap_result: GapDetectionResult,
    ticket_data: dict[str, str | None],
    conv_data: dict[str, str | None],
) -> str:
    """Handle SAME_KNOWLEDGE: log CONFIRMED event, boost confidence, add lineage link.

    Returns:
        learning_event_id
    """
    sb = get_supabase()
    now = datetime.now(UTC).isoformat()
    event_id = f"LE-{uuid.uuid4().hex[:12]}"

    best_match_id = gap_result.decision.best_match_source_id or "unknown"
    similarity = gap_result.decision.similarity_score

    # Create auto-approved CONFIRMED event
    sb.table("learning_events").insert(
        {
            "event_id": event_id,
            "trigger_ticket_number": ticket_number,
            "detected_gap": (
                f"Knowledge confirmed: existing corpus entry {best_match_id} "
                f"(similarity={similarity:.3f}) covers this ticket's resolution."
            ),
            "event_type": "CONFIRMED",
            "proposed_kb_article_id": None,
            "flagged_kb_article_id": None,
            "draft_summary": f"Existing knowledge validated by ticket {ticket_number}",
            "final_status": "Approved",
            "reviewer_role": "System",
            "event_timestamp": now,
        }
    ).execute()

    # Boost confidence on the matching corpus entry
    if best_match_id != "unknown":
        settings = get_settings()
        sb.rpc(
            "update_corpus_confidence",
            {
                "p_source_type": "KB",
                "p_source_id": best_match_id,
                "p_delta": settings.confidence_delta_resolved,
                "p_increment_usage": True,
            },
        ).execute()

    # Add lineage link: ticket → existing KB
    sb.table("kb_lineage").insert(
        {
            "kb_article_id": best_match_id,
            "source_type": "Ticket",
            "source_id": ticket_number,
            "relationship": "REFERENCES",
            "evidence_snippet": (
                f"Ticket {ticket_number} resolution confirmed existing knowledge "
                f"(similarity={similarity:.3f})"
            ),
            "event_timestamp": now,
        }
    ).execute()

    logger.info(
        "SAME_KNOWLEDGE: ticket=%s matched=%s similarity=%.3f",
        ticket_number,
        best_match_id,
        similarity,
    )

    return event_id


async def _handle_contradiction(
    ticket_number: str,
    gap_result: GapDetectionResult,
    ticket_data: dict[str, str | None],
    conv_data: dict[str, str | None],
    logs: list[RetrievalLogEntry],
) -> tuple[str, str]:
    """Handle CONTRADICTS: draft replacement KB, flag existing KB, create learning event.

    Returns:
        (learning_event_id, drafted_kb_article_id)
    """
    sb = get_supabase()
    now = datetime.now(UTC).isoformat()

    flagged_kb_id = gap_result.decision.best_match_source_id or "unknown"
    similarity = gap_result.decision.similarity_score

    # Fetch the existing KB article content for context
    existing_kb_content = ""
    if flagged_kb_id != "unknown":
        try:
            kb_row = (
                sb.table("knowledge_articles")
                .select("title, body")
                .eq("kb_article_id", flagged_kb_id)
                .single()
                .execute()
            )
            existing_kb_data = cast(dict[str, str], kb_row.data)
            existing_kb_content = (
                f"EXISTING ARTICLE TITLE: {existing_kb_data.get('title', 'N/A')}\n"
                f"EXISTING ARTICLE BODY:\n{existing_kb_data.get('body', 'N/A')[:2000]}"
            )
        except Exception:
            logger.warning("Could not fetch existing KB article %s", flagged_kb_id)

    # Draft replacement article
    draft = await _draft_replacement_kb_article(
        ticket_data, conv_data, logs, existing_kb_content
    )

    # Save draft as new KB article
    kb_article_id = f"KB-SYN-{uuid.uuid4().hex[:8].upper()}"
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

    # Create CONTRADICTION learning event
    event_id = f"LE-{uuid.uuid4().hex[:12]}"
    sb.table("learning_events").insert(
        {
            "event_id": event_id,
            "trigger_ticket_number": ticket_number,
            "detected_gap": (
                f"Contradiction detected: ticket resolution differs from existing "
                f"KB article {flagged_kb_id} (similarity={similarity:.3f}). "
                f"Reason: {gap_result.decision.reasoning}"
            ),
            "event_type": "CONTRADICTION",
            "proposed_kb_article_id": kb_article_id,
            "flagged_kb_article_id": flagged_kb_id,
            "draft_summary": draft.title,
            "final_status": None,
            "event_timestamp": now,
        }
    ).execute()

    # Create lineage for the draft
    _create_lineage_records(kb_article_id, ticket_number, ticket_data, conv_data, now)

    # Embed the draft into retrieval_corpus (as Draft, pending review)
    _embed_kb_article(kb_article_id, draft)

    logger.info(
        "CONTRADICTS: ticket=%s flagged=%s new_draft=%s similarity=%.3f",
        ticket_number,
        flagged_kb_id,
        kb_article_id,
        similarity,
    )

    return event_id, kb_article_id


async def _handle_new_knowledge(
    ticket_number: str,
    ticket_data: dict[str, str | None],
    conv_data: dict[str, str | None],
    logs: list[RetrievalLogEntry],
) -> tuple[str, str]:
    """Handle NEW_KNOWLEDGE: draft new KB article, create lineage + learning event, embed.

    Returns:
        (learning_event_id, kb_article_id)
    """
    sb = get_supabase()

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
            "event_type": "GAP",
            "proposed_kb_article_id": kb_article_id,
            "flagged_kb_article_id": None,
            "draft_summary": draft.title,
            "final_status": None,
            "event_timestamp": now,
        }
    ).execute()

    _create_lineage_records(kb_article_id, ticket_number, ticket_data, conv_data, now)
    _embed_kb_article(kb_article_id, draft)

    logger.info(
        "NEW_KNOWLEDGE: ticket=%s drafted=%s",
        ticket_number,
        kb_article_id,
    )

    return event_id, kb_article_id


# ── KB drafting helpers ──────────────────────────────────────────────


async def _draft_kb_article(
    ticket: dict[str, str | None],
    conversation: dict[str, str | None],
    logs: list[RetrievalLogEntry],
) -> KBDraftFromGap:
    """Use the LLM to draft a NEW KB article from ticket context."""
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


async def _draft_replacement_kb_article(
    ticket: dict[str, str | None],
    conversation: dict[str, str | None],
    logs: list[RetrievalLogEntry],
    existing_kb_content: str,
) -> KBDraftFromGap:
    """Use the LLM to draft a REPLACEMENT KB article that corrects existing knowledge."""
    queries = "\n".join(f"  - {log.query_text}" for log in logs)

    prompt = f"""An existing knowledge base article appears to be OUTDATED or INCORRECT based on
a recently resolved support ticket. Draft an updated replacement article.

{existing_kb_content}

---

TICKET THAT CONTRADICTS THE ABOVE:
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

SEARCH QUERIES USED:
{queries}

Create an updated KB article that incorporates the correct resolution from this ticket.
Keep any still-valid information from the existing article, but correct what is outdated."""

    system_prompt = """You are a technical writer updating an existing knowledge base article
that has been found to contain outdated or incorrect information. Your updated article must:
- Correct the outdated information based on the new ticket resolution
- Preserve any still-valid content from the original article
- Be clear, actionable, and searchable
- Include the updated resolution steps"""

    return await generate_structured_output(
        prompt=prompt,
        output_schema=KBDraftFromGap,
        system_prompt=system_prompt,
        temperature=0,
    )


# ── Shared helpers ───────────────────────────────────────────────────


def _build_gap_description(logs: list[RetrievalLogEntry]) -> str:
    """Summarize what queries failed for the gap detection record."""
    if not logs:
        return "No retrieval attempts were made during support. Knowledge gap detected via post-close analysis."
    queries = [log.query_text for log in logs]
    joined = "; ".join(queries[:5])
    return f"{len(queries)} retrieval attempts during support. Queries: {joined}"


def _create_lineage_records(
    kb_article_id: str,
    ticket_number: str,
    ticket_data: dict[str, str | None],
    conversation: dict[str, str | None],
    timestamp: str,
) -> None:
    """Create 3 kb_lineage records (CREATED_FROM Ticket, CREATED_FROM Conversation, REFERENCES Script)."""
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
            evidence_snippet=f"KB drafted from ticket {ticket_number}",
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
    """Embed the drafted KB article into retrieval_corpus using the RAG embedder."""
    sb = get_supabase()
    embedder = Embedder()
    embedding = embedder.embed(draft.body)

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


def _apply_contradiction_approval(
    flagged_kb_id: str,
    replacement_kb_id: str,
    now: str,
) -> None:
    """Apply an approved contradiction: update old KB with new content, clean up draft."""
    sb = get_supabase()

    # Fetch the replacement draft content
    draft_row = (
        sb.table("knowledge_articles")
        .select("title, body, tags, module, category")
        .eq("kb_article_id", replacement_kb_id)
        .single()
        .execute()
    )
    draft_data = cast(dict[str, str | None], draft_row.data)

    # Update the original KB article with the corrected content
    sb.table("knowledge_articles").update(
        {
            "title": draft_data.get("title"),
            "body": draft_data.get("body"),
            "tags": draft_data.get("tags"),
            "module": draft_data.get("module"),
            "category": draft_data.get("category"),
            "updated_at": now,
            "status": "Active",
        }
    ).eq("kb_article_id", flagged_kb_id).execute()

    # Re-embed the updated original KB article
    body = draft_data.get("body", "")
    if body:
        embedder = Embedder()
        embedding = embedder.embed(body)
        sb.table("retrieval_corpus").update(
            {
                "title": draft_data.get("title"),
                "content": body,
                "category": draft_data.get("category"),
                "module": draft_data.get("module"),
                "tags": draft_data.get("tags"),
                "embedding": embedding,
                "updated_at": now,
            }
        ).eq("source_type", "KB").eq("source_id", flagged_kb_id).execute()

    # Archive the draft (it's been merged into the original)
    sb.table("knowledge_articles").update(
        {"status": "Archived", "updated_at": now}
    ).eq("kb_article_id", replacement_kb_id).execute()

    # Remove the draft from retrieval_corpus (original is now updated)
    sb.table("retrieval_corpus").delete().eq("source_type", "KB").eq(
        "source_id", replacement_kb_id
    ).execute()

    logger.info(
        "Contradiction approved: updated %s with content from %s",
        flagged_kb_id,
        replacement_kb_id,
    )
