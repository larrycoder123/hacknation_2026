"""Learning pipeline API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Path
from postgrest.exceptions import APIError

from app.schemas.learning import (
    LearningEventRecord,
    ReviewDecision,
    SelfLearningResult,
)
from app.services import learning_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["learning"])


@router.post(
    "/tickets/{ticket_number}/learn",
    response_model=SelfLearningResult,
)
async def post_conversation_learn(
    ticket_number: str = Path(min_length=1, max_length=50),
) -> SelfLearningResult:
    """Run the self-learning pipeline after a ticket is closed.

    Two-stage pipeline:
    1. Score retrieval logs — update confidence on corpus entries.
    2. Fresh gap detection — RAG search + LLM classification (SAME/CONTRADICTS/NEW).
    3. Act — boost confidence, draft replacement, or draft new KB article.
    """
    try:
        return await learning_service.run_post_conversation_learning(ticket_number)
    except APIError as exc:
        logger.exception("Supabase error for ticket %s", ticket_number)
        if "0 rows" in str(exc) or "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Ticket not found") from exc
        raise HTTPException(status_code=502, detail="Database error") from exc
    except Exception as exc:
        logger.exception("Unexpected error in learn pipeline for ticket %s", ticket_number)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post(
    "/learning-events/{event_id}/review",
    response_model=LearningEventRecord,
)
async def review_learning_event(
    event_id: str = Path(pattern=r"^LE-[a-f0-9]{12}$"),
    body: ReviewDecision = ...,
) -> LearningEventRecord:
    """Approve or reject a drafted KB article from the learning pipeline.

    For GAP events: Approved activates the KB article. Rejected archives it.
    For CONTRADICTION events: Approved replaces old KB with corrected content.
    Rejected keeps existing KB and discards the draft.
    """
    try:
        return await learning_service.review_learning_event(event_id, body)
    except APIError as exc:
        logger.exception("Supabase error for event %s", event_id)
        if "0 rows" in str(exc) or "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Learning event not found") from exc
        raise HTTPException(status_code=502, detail="Database error") from exc
    except Exception as exc:
        logger.exception("Unexpected error reviewing event %s", event_id)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
