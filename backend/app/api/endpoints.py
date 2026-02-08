from fastapi import APIRouter, HTTPException
from typing import List, Optional

from ..schemas.actions import SuggestedAction
from ..schemas.tickets import CloseTicketPayload, CloseTicketResponse, Ticket
from ..schemas.messages import Message, TicketConversation
from ..schemas.knowledge import KnowledgeArticle
from ..data.tickets import MOCK_TICKETS, MOCK_CONVERSATIONS
from ..data.suggestions import MOCK_SUGGESTIONS
from ..services import knowledge_service

router = APIRouter()


@router.get("/tickets", response_model=List[Ticket])
async def get_tickets():
    """Get all tickets."""
    return list(MOCK_TICKETS.values())


@router.get("/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str):
    """Get a single ticket by ID."""
    if ticket_id not in MOCK_TICKETS:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return MOCK_TICKETS[ticket_id]


@router.get("/tickets/{ticket_id}/messages", response_model=List[Message])
async def get_ticket_messages(ticket_id: str):
    """Get all messages for a ticket."""
    if ticket_id not in MOCK_TICKETS:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return MOCK_CONVERSATIONS.get(ticket_id, [])


@router.get("/tickets/{ticket_id}/conversation", response_model=TicketConversation)
async def get_ticket_conversation(ticket_id: str):
    """Get complete conversation data for a ticket."""
    if ticket_id not in MOCK_TICKETS:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketConversation(
        ticket_id=ticket_id, messages=MOCK_CONVERSATIONS.get(ticket_id, [])
    )


@router.get("/tickets/{ticket_id}/suggested-actions", response_model=List[SuggestedAction])
async def get_suggested_actions(ticket_id: str):
    """Get AI-suggested actions for a ticket."""
    return MOCK_SUGGESTIONS


@router.post("/tickets/{ticket_id}/close", response_model=CloseTicketResponse)
async def close_ticket(ticket_id: str, payload: CloseTicketPayload):
    """
    Close a ticket and optionally generate a knowledge article.

    If add_to_knowledge_base is true, this will:
    1. Fetch the ticket and conversation
    2. Use the LLM to generate a knowledge article
    3. TODO: Store the article in the database
    """
    if ticket_id not in MOCK_TICKETS:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = MOCK_TICKETS[ticket_id]
    messages = MOCK_CONVERSATIONS.get(ticket_id, [])

    knowledge_article: Optional[KnowledgeArticle] = None

    # Generate knowledge article if requested
    if payload.add_to_knowledge_base and payload.resolution_type == "Resolved Successfully":
        try:
            knowledge_article = await knowledge_service.generate_knowledge_article(
                ticket_id=ticket_id,
                ticket_subject=ticket.subject,
                messages=messages,
                resolution_notes=payload.notes,
            )

            # TODO: Save knowledge_article to database
            print(f"Generated knowledge article for ticket {ticket_id}:")
            print(knowledge_article.model_dump_json(indent=2))

        except Exception as e:
            # Log error but don't fail the ticket closure
            print(f"Failed to generate knowledge article: {e}")

    # Update ticket status in mock data
    MOCK_TICKETS[ticket_id] = ticket.model_copy(update={"status": "Resolved"})

    return CloseTicketResponse(
        status="success",
        message=f"Ticket {ticket_id} closed successfully",
        knowledge_article=knowledge_article,
    )
