"""
Knowledge Article Service.

This service handles the generation of knowledge articles from resolved tickets
using the LLM client.
"""

from typing import List, Optional
from ..core.llm_client import get_llm_client, LLMMessage
from ..schemas.knowledge import KnowledgeArticle
from ..schemas.messages import Message

class KnowledgeService:
    """
    Service for generating and managing knowledge articles.
    
    Uses LLM to analyze ticket conversations and generate structured
    knowledge articles for the knowledge base.
    """
    
    def __init__(self):
        self.llm = get_llm_client()
    
    def _format_conversation_for_llm(
        self,
        messages: List[Message],
        resolution_notes: Optional[str] = None,
    ) -> str:
        """Format ticket conversation into a readable string for the LLM."""
        conversation_text = "TICKET CONVERSATION:\n"
        conversation_text += "=" * 40 + "\n"
        
        for msg in messages:
            sender_label = {
                "customer": "CUSTOMER",
                "agent": "SUPPORT AGENT",
                "system": "SYSTEM"
            }.get(msg.sender, msg.sender.upper())
            
            conversation_text += f"\n[{msg.timestamp}] {sender_label}:\n{msg.content}\n"
        
        conversation_text += "\n" + "=" * 40
        
        if resolution_notes:
            conversation_text += f"\n\nAGENT RESOLUTION NOTES:\n{resolution_notes}"
        
        return conversation_text
    
    async def generate_knowledge_article(
        self,
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
        conversation_text = self._format_conversation_for_llm(messages, resolution_notes)
        
        system_prompt = """You are a technical writer creating knowledge base articles from resolved support tickets.

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

        llm_messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        
        article = await self.llm.structured_output(
            messages=llm_messages,
            output_schema=KnowledgeArticle,
            temperature=0.4,
        )
        
        # Merge custom tags if provided
        if custom_tags:
            article.tags = list(set(article.tags + custom_tags))
        
        return article

# Singleton instance
_knowledge_service: Optional[KnowledgeService] = None

def get_knowledge_service() -> KnowledgeService:
    """Get or create the knowledge service instance."""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
