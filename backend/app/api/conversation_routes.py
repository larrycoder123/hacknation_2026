import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path

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

# Source type to SuggestedAction type mapping
_SOURCE_TYPE_MAP = {"SCRIPT": "script", "KB": "response", "TICKET_RESOLUTION": "action"}


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
    """Retrieve AI-generated suggested actions for resolving a conversation.

    Uses RAG to search the retrieval_corpus (scripts, KB articles, ticket
    resolutions) based on the conversation context and returns the top hits
    as suggested actions for the support agent.

    Falls back to mock suggestions if RAG is unavailable.
    """
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = MOCK_CONVERSATIONS[conversation_id]
    messages = MOCK_MESSAGES.get(conversation_id, [])

    # Build query from conversation context
    query_parts = [conversation.subject]
    # Add last customer message for more context
    for msg in reversed(messages):
        if msg.sender == "customer":
            query_parts.append(msg.content[:300])
            break
    query = ". ".join(query_parts)

    try:
        from app.rag.agent.graph import run_rag

        result = await asyncio.to_thread(
            run_rag,
            question=query,
            category=getattr(conversation, "category", None),
            top_k=5,
            conversation_id=conversation_id,
        )

        actions: list[SuggestedAction] = []
        for hit in result.top_hits:
            action_type = _SOURCE_TYPE_MAP.get(hit.source_type, "action")
            score = hit.rerank_score if hit.rerank_score is not None else hit.similarity
            actions.append(SuggestedAction(
                id=hit.source_id,
                type=action_type,
                confidence_score=round(score, 2),
                title=hit.title or hit.source_id,
                description=hit.content[:200] + "..." if len(hit.content) > 200 else hit.content,
                content=hit.content,
                source=f"{hit.source_type}: {hit.source_id}",
            ))

        return actions if actions else MOCK_SUGGESTIONS

    except Exception:
        logger.exception("RAG failed for conversation %s, falling back to mock", conversation_id)
        return MOCK_SUGGESTIONS


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
    warnings: list[str] = []

    # Generate ticket if requested
    if payload.create_ticket and payload.resolution_type == "Resolved Successfully":
        try:
            ticket = await ticket_service.generate_ticket(
                conversation_id=conversation_id,
                conversation_subject=conversation.subject,
                messages=messages,
                resolution_notes=payload.notes,
            )

            logger.info("Generated ticket for conversation %s", conversation_id)

            # Persist to DB so the self-learning pipeline can pick it up
            try:
                tn = await asyncio.to_thread(
                    ticket_service.save_ticket_to_db,
                    ticket,
                    conversation_id,
                    conversation.priority,
                )
                ticket.ticket_number = tn
            except Exception:
                logger.exception("Failed to save ticket to DB for conversation %s", conversation_id)
                warnings.append("Ticket was generated but could not be saved to the database.")

        except Exception:
            logger.exception("Failed to generate ticket for conversation %s", conversation_id)

    # Update conversation status in mock data
    MOCK_CONVERSATIONS[conversation_id] = conversation.model_copy(update={"status": "Resolved"})

    # Run self-learning pipeline (synchronous for demo)
    # Only run if ticket was saved to DB (ticket_number assigned)
    if ticket and getattr(ticket, "ticket_number", None) and payload.resolution_type == "Resolved Successfully":
        try:
            ticket_number = ticket.ticket_number
            resolved = payload.resolution_type == "Resolved Successfully"
            learning_result = await learning_service.run_post_conversation_learning(
                ticket_number,
                resolved=resolved,
                conversation_id=conversation_id,
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
        warnings=warnings,
    )
