"""Ticket generation service using LangChain."""

import logging
import uuid
from datetime import UTC, datetime
from typing import List, Optional

from postgrest.exceptions import APIError

from ..core.llm import generate_structured_output
from ..db.client import get_supabase
from ..schemas.tickets import Priority, Ticket, TicketDBRow
from ..schemas.messages import Message

logger = logging.getLogger(__name__)


def _format_conversation(
    messages: List[Message],
    resolution_notes: Optional[str] = None,
) -> str:
    """Format conversation messages into a readable string for the LLM."""
    lines = ["CONVERSATION:", "=" * 40]

    for msg in messages:
        sender_label = {
            "customer": "CUSTOMER",
            "agent": "SUPPORT AGENT",
            "system": "SYSTEM",
        }.get(msg.sender, msg.sender.upper())
        lines.append(f"\n[{msg.timestamp}] {sender_label}:\n{msg.content}")

    lines.append("\n" + "=" * 40)

    if resolution_notes:
        lines.append(f"\n\nAGENT RESOLUTION NOTES:\n{resolution_notes}")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are a technical writer creating ticket records from resolved support conversations.

Your task is to analyze the support conversation and create a comprehensive, well-structured ticket (case record) that can help:
1. Future support agents handle similar issues quickly
2. Customers potentially self-serve if the article is made public
3. Developers understand recurring issues

Guidelines:
- Extract the core problem and its solution
- Identify any error codes, product features, or technical terms mentioned
- Create clear, actionable resolution steps
- Generate relevant tags for searchability
- Write a customer-friendly communication template if applicable
- Keep the language professional but accessible"""


async def generate_ticket(
    conversation_id: str,
    conversation_subject: str,
    messages: List[Message],
    resolution_notes: Optional[str] = None,
    custom_tags: Optional[List[str]] = None,
) -> Ticket:
    """
    Generate a ticket (case record) from a resolved conversation.
    """
    conversation_text = _format_conversation(messages, resolution_notes)

    user_prompt = f"""Please analyze this resolved support conversation and create a ticket record.

CONVERSATION ID: {conversation_id}
ORIGINAL SUBJECT: {conversation_subject}

{conversation_text}

Create a ticket record with:
- A clear, searchable subject line
- A description of the issue/problem
- The resolution that was applied
- Relevant tags for categorization
- Any other relevant fields you can extract from the conversation"""

    ticket = await generate_structured_output(
        prompt=user_prompt,
        output_schema=Ticket,
        system_prompt=SYSTEM_PROMPT,
    )

    # Merge custom tags if provided
    if custom_tags:
        ticket.tags = list(set(ticket.tags + custom_tags))

    return ticket


_MAX_COLLISION_RETRIES = 3


def _generate_ticket_number() -> str:
    """Generate a ticket number in CS-{8-char-hex} format."""
    return f"CS-{uuid.uuid4().hex[:8].upper()}"


def save_ticket_to_db(
    ticket: Ticket,
    conversation_id: str,
    priority: Priority,
) -> str:
    """Persist the LLM-generated ticket to Supabase.

    Inserts a minimal ``conversations`` row (required by FK) then the
    ``tickets`` row.  Retries with a fresh ticket number on unique-constraint
    collisions.  Returns the generated ``ticket_number``.
    """
    sb = get_supabase()

    for attempt in range(_MAX_COLLISION_RETRIES):
        ticket_number = _generate_ticket_number()
        now = datetime.now(UTC).isoformat()

        row = TicketDBRow(
            ticket_number=ticket_number,
            created_at=now,
            closed_at=now,
            status="Closed",
            priority=priority,
            subject=ticket.subject,
            description=ticket.description,
            resolution=ticket.resolution,
            tags=",".join(ticket.tags),
            case_type="Incident",
        )

        try:
            # FK: tickets.ticket_number -> conversations.ticket_number
            sb.table("conversations").insert(
                {
                    "ticket_number": ticket_number,
                    "conversation_id": conversation_id,
                    "issue_summary": ticket.subject,
                }
            ).execute()
        except APIError as exc:
            if "duplicate" in str(exc).lower() or "23505" in str(exc):
                if attempt < _MAX_COLLISION_RETRIES - 1:
                    logger.warning("Collision on ticket_number %s, retrying", ticket_number)
                    continue
            raise

        try:
            sb.table("tickets").insert(row.model_dump()).execute()
        except Exception:
            # Compensating delete to avoid orphaned conversations row
            try:
                sb.table("conversations").delete().eq(
                    "ticket_number", ticket_number
                ).execute()
            except Exception:
                logger.exception("Failed to clean up orphaned conversations row %s", ticket_number)
            raise

        logger.info("Saved ticket %s for conversation %s", ticket_number, conversation_id)
        return ticket_number

    raise RuntimeError("Failed to generate a unique ticket number")
