import logging

from fastapi import APIRouter, HTTPException, Path
from typing import List, Optional

logger = logging.getLogger(__name__)

from ..schemas.actions import SuggestedAction
from ..schemas.conversations import CloseConversationPayload, CloseConversationResponse, Conversation
from ..schemas.messages import Message
from ..schemas.tickets import Ticket
from ..data.conversations import MOCK_CONVERSATIONS, MOCK_MESSAGES
from ..data.suggestions import MOCK_SUGGESTIONS
from ..services import ticket_service

router = APIRouter()


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


@router.post("/conversations/{conversation_id}/close", response_model=CloseConversationResponse)
async def close_conversation(conversation_id: str = Path(min_length=1, max_length=50), payload: CloseConversationPayload = ...):
    """
    Close a conversation and optionally generate a ticket (case record).

    If create_ticket is true and the conversation was resolved successfully,
    an LLM generates a ticket from the conversation.
    """
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = MOCK_CONVERSATIONS[conversation_id]
    messages = MOCK_MESSAGES.get(conversation_id, [])

    ticket: Optional[Ticket] = None

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
            logger.info("Generated ticket for conversation %s: %s", conversation_id, ticket.model_dump_json())

        except Exception:
            logger.exception("Failed to generate ticket for conversation %s", conversation_id)

    # Update conversation status in mock data
    MOCK_CONVERSATIONS[conversation_id] = conversation.model_copy(update={"status": "Resolved"})

    return CloseConversationResponse(
        status="success",
        message=f"Conversation {conversation_id} closed successfully",
        ticket=ticket,
    )
