"""Ticket generation service using LangChain."""

from typing import List, Optional
from ..core.llm import generate_structured_output
from ..schemas.tickets import Ticket
from ..schemas.messages import Message


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
