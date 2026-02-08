from fastapi import APIRouter, HTTPException
from typing import List, Optional

from ..schemas.actions import SuggestedAction
from ..schemas.tickets import CloseTicketPayload, CloseTicketResponse, Ticket
from ..schemas.messages import Message, TicketConversation
from ..schemas.knowledge import KnowledgeArticle
from ..services.knowledge_service import get_knowledge_service

router = APIRouter()

# Mock data for tickets
MOCK_TICKETS: dict[str, Ticket] = {
    "1024": Ticket(
        id="1024",
        customer_name="Alice Johnson",
        subject="Cannot access property certifications",
        priority="High",
        status="Open",
        time_ago="5m",
        last_message="I am getting Error 505 when trying to view certificates.",
    ),
    "1025": Ticket(
        id="1025",
        customer_name="Bob Smith",
        subject="Billing question for March",
        priority="Medium",
        status="Open",
        time_ago="12m",
        last_message="Why was I charged twice?",
    ),
    "1026": Ticket(
        id="1026",
        customer_name="Charlie Brown",
        subject="Feature request: Dark mode",
        priority="Low",
        status="Pending",
        time_ago="1h",
        last_message="Any updates on dark mode support?",
    ),
    "1027": Ticket(
        id="1027",
        customer_name="Diana Prince",
        subject="Login issues on mobile",
        priority="High",
        status="Open",
        time_ago="2h",
        last_message="The app crashes when I try to log in.",
    ),
    "1028": Ticket(
        id="1028",
        customer_name="Evan Wright",
        subject="Where can I find the API key?",
        priority="Medium",
        status="Resolved",
        time_ago="1d",
        last_message="Found it, thanks!",
    ),
}

# Mock conversations data
MOCK_CONVERSATIONS: dict[str, list[Message]] = {
    "1024": [
        Message(
            id="m1",
            ticket_id="1024",
            sender="customer",
            content="Hi, I am trying to access the property certifications for my new listing, but I keep getting an Error 505 page.",
            timestamp="10:30 AM",
        ),
        Message(
            id="m2",
            ticket_id="1024",
            sender="agent",
            content="Hello Alice, I can help you with that. Let me check your account details.",
            timestamp="10:32 AM",
        ),
        Message(
            id="m3",
            ticket_id="1024",
            sender="customer",
            content="Okay, thanks. It is for property ID prop-8821.",
            timestamp="10:33 AM",
        ),
    ],
    "1025": [
        Message(
            id="m4",
            ticket_id="1025",
            sender="customer",
            content="I see two charges for March on my statement. Can you explain?",
            timestamp="10:15 AM",
        ),
        Message(
            id="m5",
            ticket_id="1025",
            sender="agent",
            content="Hi Bob, I'd be happy to look into this for you. Could you provide the last 4 digits of the card used?",
            timestamp="10:18 AM",
        ),
        Message(
            id="m6",
            ticket_id="1025",
            sender="customer",
            content="Sure, it ends in 4521.",
            timestamp="10:20 AM",
        ),
    ],
    "1026": [
        Message(
            id="m7",
            ticket_id="1026",
            sender="customer",
            content="Hey, I was wondering if you have any plans to add dark mode? It would be really helpful for late night work.",
            timestamp="09:00 AM",
        ),
        Message(
            id="m8",
            ticket_id="1026",
            sender="agent",
            content="Hi Charlie! Thanks for the suggestion. Dark mode is on our roadmap for Q2 this year.",
            timestamp="09:15 AM",
        ),
        Message(
            id="m9",
            ticket_id="1026",
            sender="customer",
            content="Any updates on dark mode support?",
            timestamp="10:00 AM",
        ),
    ],
    "1027": [
        Message(
            id="m10",
            ticket_id="1027",
            sender="customer",
            content="The app crashes when I try to log in on my iPhone. It worked fine yesterday.",
            timestamp="08:30 AM",
        ),
        Message(
            id="m11",
            ticket_id="1027",
            sender="agent",
            content="Sorry to hear that, Diana. What iOS version are you running?",
            timestamp="08:35 AM",
        ),
        Message(
            id="m12",
            ticket_id="1027",
            sender="customer",
            content="iOS 17.3.",
            timestamp="08:36 AM",
        ),
        Message(
            id="m13",
            ticket_id="1027",
            sender="agent",
            content="Thank you. We've identified an issue with the latest app update on iOS 17.3. Our team is working on a fix. In the meantime, try force-closing the app and logging in again.",
            timestamp="08:40 AM",
        ),
    ],
    "1028": [
        Message(
            id="m14",
            ticket_id="1028",
            sender="customer",
            content="Where can I find my API key for the developer dashboard?",
            timestamp="Yesterday 2:00 PM",
        ),
        Message(
            id="m15",
            ticket_id="1028",
            sender="agent",
            content="Hi Evan! You can find your API key in Settings > Developer > API Keys. Let me know if you need further help!",
            timestamp="Yesterday 2:05 PM",
        ),
        Message(
            id="m16",
            ticket_id="1028",
            sender="customer",
            content="Found it, thanks!",
            timestamp="Yesterday 2:10 PM",
        ),
    ],
}

# Mock suggested actions
MOCK_SUGGESTIONS = [
    {
        "id": "act_8821_a",
        "type": "script",
        "confidence_score": 0.98,
        "title": "Fix Certifications Script",
        "description": "Updates the user settings table to force a refresh of the property certification status.",
        "content": "UPDATE settings \nSET cert_status = 'pending_review' \nWHERE property_id = 'prop-8821';",
        "source": "Ticket #9942"
    },
    {
        "id": "act_8821_b",
        "type": "response",
        "confidence_score": 0.85,
        "title": "Explain Compliance Delay",
        "description": "Standard apology template for compliance delays.",
        "content": "Knowledge Base Article: Compliance Delays\\n\\nIssue: Customers may experience delays in property certification syncing due to high load on the verification server. This typically manifests as a 505 error on the certifications page.\\n\\nResolution Steps:\\n1. Verify the property ID.\\n2. Check the sync status in the admin panel.\\n3. If 'Pending', advise the customer to wait 2-4 hours.\\n4. If 'Error', run the 'Fix Certifications Script'.\\n\\nCustomer Communication Template:\\n\\\"I apologize for the inconvenience. It appears our certification verification system is currently under heavy load, which is causing a delay in syncing your property details. This usually resolves within 2-4 hours. However, since you are seeing an error, I can manually trigger a refresh for you. Would you like me to do that now?\\\"",
        "source": "Knowledge Base Art. 12"
    },
]


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
        ticket_id=ticket_id,
        messages=MOCK_CONVERSATIONS.get(ticket_id, [])
    )


@router.get("/tickets/{ticket_id}/suggested-actions", response_model=List[SuggestedAction])
async def get_suggested_actions(ticket_id: str):
    """Get AI-suggested actions for a ticket."""
    # In a real app, logic would filter by ticket_id or context
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
            knowledge_service = get_knowledge_service()
            knowledge_article = await knowledge_service.generate_knowledge_article(
                ticket_id=ticket_id,
                ticket_subject=ticket.subject,
                messages=messages,
                resolution_notes=payload.notes,
            )
            
            # TODO: Save knowledge_article to database
            # Example:
            # await db.knowledge_articles.insert_one(knowledge_article.model_dump())
            
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
