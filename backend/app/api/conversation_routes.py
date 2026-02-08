import asyncio
import logging
from typing import List, Optional
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from ..data.conversations import MOCK_CONVERSATIONS, MOCK_MESSAGES
from ..data.suggestions import MOCK_SUGGESTIONS
from ..schemas.actions import SuggestedAction
from ..schemas.conversations import CloseConversationPayload, CloseConversationResponse, Conversation
from ..schemas.learning import SelfLearningResult
from ..schemas.messages import Message
from ..schemas.tickets import Ticket
from ..services import learning_service, ticket_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response models for /ask ───────────────────────────────


class AskCopilotRequest(BaseModel):
    """Payload for asking the copilot a question."""

    question: str = Field(min_length=1, max_length=2000)
    ticket_number: str | None = Field(default=None, max_length=50)


class AskCopilotResponse(BaseModel):
    """Response from the copilot RAG pipeline."""

    answer: str
    citations: list[dict] = Field(default_factory=list)
    confidence: str = "medium"
    retrieval_queries: list[str] = Field(default_factory=list)


# ── Conversation endpoints ───────────────────────────────────────────


@router.get("/conversations", response_model=List[Conversation])
async def get_conversations():
    """Retrieve all support conversations."""
    return list(MOCK_CONVERSATIONS.values())


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str = Path(min_length=1, max_length=50)):
    """Retrieve a single conversation by ID."""
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return MOCK_CONVERSATIONS[conversation_id]


@router.get("/conversations/{conversation_id}/messages", response_model=List[Message])
async def get_conversation_messages(conversation_id: str = Path(min_length=1, max_length=50)):
    """Retrieve the message history for a conversation."""
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return MOCK_MESSAGES.get(conversation_id, [])


@router.get("/conversations/{conversation_id}/suggested-actions", response_model=List[SuggestedAction])
async def get_suggested_actions(conversation_id: str = Path(min_length=1, max_length=50)):
    """Retrieve AI-generated suggested actions for resolving a conversation."""
    return MOCK_SUGGESTIONS


# ── Copilot endpoint ─────────────────────────────────────────────────


@router.post(
    "/conversations/{conversation_id}/ask",
    response_model=AskCopilotResponse,
)
async def ask_copilot(
    conversation_id: str = Path(min_length=1, max_length=50),
    body: AskCopilotRequest = ...,
) -> AskCopilotResponse:
    """Ask the Customer Support Copilot a question using RAG.

    Searches the retrieval_corpus (scripts, KB articles, ticket resolutions)
    and returns an answer with citations. Each call writes to retrieval_log
    for the learning pipeline to use later.
    """
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = MOCK_CONVERSATIONS[conversation_id]

    try:
        from app.rag.agent.graph import run_rag

        result = run_rag(
            question=body.question,
            category=getattr(conversation, "category", None),
            ticket_number=body.ticket_number,
        )

        citations = [
            {
                "source_type": c.source_type,
                "source_id": c.source_id,
                "title": c.title,
                "quote": c.quote,
            }
            for c in result.citations
        ]

        return AskCopilotResponse(
            answer=result.answer,
            citations=citations,
            confidence=getattr(result, "confidence", "medium"),
            retrieval_queries=result.retrieval_queries,
        )

    except Exception:
        logger.exception("RAG failed for conversation %s", conversation_id)
        raise HTTPException(status_code=500, detail="Copilot query failed")


# ── Close conversation ───────────────────────────────────────────────


@router.post("/conversations/{conversation_id}/close", response_model=CloseConversationResponse)
async def close_conversation(
    conversation_id: str = Path(min_length=1, max_length=50),
    payload: CloseConversationPayload = ...,
):
    """Close a conversation, generate a ticket, and run the self-learning pipeline.

    If create_ticket is true and the conversation was resolved successfully,
    an LLM generates a ticket from the conversation. Then the learning pipeline
    runs synchronously to detect gaps and update the knowledge base.
    """
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = MOCK_CONVERSATIONS[conversation_id]
    messages = MOCK_MESSAGES.get(conversation_id, [])

    ticket: Optional[Ticket] = None
    learning_result: Optional[SelfLearningResult] = None

    # Generate ticket if requested
    if payload.create_ticket and payload.resolution_type == "Resolved Successfully":
        try:
            ticket = await ticket_service.generate_ticket(
                conversation_id=conversation_id,
                conversation_subject=conversation.subject,
                messages=messages,
                resolution_notes=payload.notes,
            )

            # TODO: Save ticket to database
            logger.info("Generated ticket for conversation %s", conversation_id)

        except Exception:
            logger.exception("Failed to generate ticket for conversation %s", conversation_id)

    # Update conversation status in mock data
    MOCK_CONVERSATIONS[conversation_id] = conversation.model_copy(update={"status": "Resolved"})

    # Run self-learning pipeline (synchronous for demo)
    if ticket and payload.resolution_type == "Resolved Successfully":
        try:
            # Use conversation_id as ticket_number for now (until real ticket IDs from DB)
            ticket_number = getattr(ticket, "ticket_number", conversation_id)
            resolved = payload.resolution_type == "Resolved Successfully"
            learning_result = await learning_service.run_post_conversation_learning(
                ticket_number, resolved=resolved
            )
            logger.info(
                "Learning pipeline completed for %s: classification=%s",
                conversation_id,
                learning_result.gap_classification,
            )
        except Exception:
            logger.exception("Learning pipeline failed for conversation %s", conversation_id)

    return CloseConversationResponse(
        status="success",
        message=f"Conversation {conversation_id} closed successfully",
        ticket=ticket,
        learning_result=learning_result,
    )
