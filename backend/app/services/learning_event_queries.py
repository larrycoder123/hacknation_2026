"""Query service for listing and filtering learning events with joined data."""

import logging
from typing import cast

from app.db.client import get_supabase
from app.schemas.learning import (
    KBArticleSummary,
    LearningEventDetail,
    LearningEventListResponse,
)

logger = logging.getLogger(__name__)


def list_learning_events(
    status: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> LearningEventListResponse:
    """List learning events with optional filters, joined with KB article and ticket data.

    Args:
        status: Filter by review status — "pending", "approved", or "rejected".
        event_type: Filter by event type — "GAP", "CONTRADICTION", or "CONFIRMED".
        limit: Max events to return.
        offset: Pagination offset.

    Returns:
        LearningEventListResponse with events and total_count.
    """
    sb = get_supabase()

    query = sb.table("learning_events").select("*", count="exact")

    # Apply status filter
    if status == "pending":
        query = query.is_("final_status", "null")
    elif status == "approved":
        query = query.eq("final_status", "Approved")
    elif status == "rejected":
        query = query.eq("final_status", "Rejected")

    # Apply event type filter
    if event_type:
        query = query.eq("event_type", event_type)

    # Order and paginate
    query = query.order("event_timestamp", desc=True)
    query = query.range(offset, offset + limit - 1)

    result = query.execute()
    rows = cast(list[dict], result.data or [])
    total_count = result.count or 0

    # Batch-fetch KB articles
    kb_ids: set[str] = set()
    for row in rows:
        if row.get("proposed_kb_article_id"):
            kb_ids.add(row["proposed_kb_article_id"])
        if row.get("flagged_kb_article_id"):
            kb_ids.add(row["flagged_kb_article_id"])

    kb_map: dict[str, KBArticleSummary] = {}
    if kb_ids:
        kb_result = (
            sb.table("knowledge_articles")
            .select("kb_article_id, title, body, tags, module, category, status")
            .in_("kb_article_id", list(kb_ids))
            .execute()
        )
        for kb_row in cast(list[dict], kb_result.data or []):
            kb_map[kb_row["kb_article_id"]] = KBArticleSummary(**kb_row)

    # Batch-fetch tickets
    ticket_numbers: set[str] = set()
    for row in rows:
        if row.get("trigger_ticket_number"):
            ticket_numbers.add(row["trigger_ticket_number"])

    ticket_map: dict[str, dict] = {}
    if ticket_numbers:
        ticket_result = (
            sb.table("tickets")
            .select("ticket_number, subject, description, resolution")
            .in_("ticket_number", list(ticket_numbers))
            .execute()
        )
        for t_row in cast(list[dict], ticket_result.data or []):
            ticket_map[t_row["ticket_number"]] = t_row

    # Assemble detail objects
    events: list[LearningEventDetail] = []
    for row in rows:
        ticket_data = ticket_map.get(row.get("trigger_ticket_number", ""), {})
        events.append(
            LearningEventDetail(
                event_id=row["event_id"],
                trigger_ticket_number=row["trigger_ticket_number"],
                detected_gap=row.get("detected_gap", ""),
                event_type=row.get("event_type", "GAP"),
                proposed_kb_article_id=row.get("proposed_kb_article_id"),
                flagged_kb_article_id=row.get("flagged_kb_article_id"),
                draft_summary=row.get("draft_summary", ""),
                final_status=row.get("final_status"),
                reviewer_role=row.get("reviewer_role"),
                event_timestamp=row.get("event_timestamp"),
                proposed_article=kb_map.get(row.get("proposed_kb_article_id", "")),
                flagged_article=kb_map.get(row.get("flagged_kb_article_id", "")),
                trigger_ticket_subject=ticket_data.get("subject"),
                trigger_ticket_description=ticket_data.get("description"),
                trigger_ticket_resolution=ticket_data.get("resolution"),
            )
        )

    return LearningEventListResponse(events=events, total_count=total_count)
