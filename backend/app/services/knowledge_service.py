"""Knowledge Article Service using LangChain."""

from typing import List, Optional
from ..core.llm import generate_structured_output
from ..schemas.knowledge import KnowledgeArticle
from ..schemas.messages import Message


def _format_conversation(
    messages: List[Message],
    resolution_notes: Optional[str] = None,
) -> str:
    """Format ticket conversation into a readable string for the LLM."""
    lines = ["TICKET CONVERSATION:", "=" * 40]

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


SYSTEM_PROMPT = """You are a technical writer creating knowledge base articles from resolved support tickets.

Your task is to analyze the support ticket conversation and create a comprehensive, well-structured knowledge article that can help:
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


async def generate_knowledge_article(
    ticket_id: str,
    ticket_subject: str,
    messages: List[Message],
    resolution_notes: Optional[str] = None,
    custom_tags: Optional[List[str]] = None,
) -> KnowledgeArticle:
    """
    Generate a knowledge article from a resolved ticket conversation.

    Args:
        ticket_id: ID of the resolved ticket
        ticket_subject: Subject/title of the ticket
        messages: List of messages in the conversation
        resolution_notes: Optional notes from the agent about the resolution
        custom_tags: Optional list of tags to include

    Returns:
        Generated KnowledgeArticle instance
    """
    conversation_text = _format_conversation(messages, resolution_notes)

    user_prompt = f"""Please analyze this resolved support ticket and create a knowledge article.

TICKET ID: {ticket_id}
ORIGINAL SUBJECT: {ticket_subject}

{conversation_text}

Create a knowledge article with:
- A clear, searchable subject line
- A description of the issue/problem
- The resolution that was applied
- Relevant tags for categorization
- Any other relevant fields you can extract from the conversation"""

    article = await generate_structured_output(
        prompt=user_prompt,
        output_schema=KnowledgeArticle,
        system_prompt=SYSTEM_PROMPT,
    )

    # Merge custom tags if provided
    if custom_tags:
        article.tags = list(set(article.tags + custom_tags))

    return article
