"""Conversation API endpoints.

Serves mock conversations and messages from app/data/, triggers RAG-powered
suggested actions, and handles the close-conversation flow (ticket generation
+ self-learning pipeline).
"""

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path

from ..data.conversations import MOCK_CONVERSATIONS, MOCK_MESSAGES
from ..data.suggestions import MOCK_SUGGESTIONS
from ..schemas.actions import ScoreBreakdown, SuggestedAction
from ..schemas.conversations import CloseConversationPayload, CloseConversationResponse, Conversation
from ..schemas.learning import SelfLearningResult
from ..schemas.messages import Message, SimulateCustomerRequest, SimulateCustomerResponse, SuggestedActionsRequest
from ..schemas.tickets import Ticket
from ..services import learning_service, ticket_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Source type to SuggestedAction type mapping
_SOURCE_TYPE_MAP = {"SCRIPT": "script",
                    "KB": "response", "TICKET_RESOLUTION": "action"}


_ADAPT_SUMMARY_PROMPT = """You are an AI assistant helping a customer support agent resolve an issue.

Given the customer's issue and the best-matching knowledge source, write a short actionable summary (3-5 sentences) that tells the agent exactly what to do. Be direct and specific.

Customer issue: {customer_issue}

Knowledge source ({source_type}):
{content}

Write a concise, agent-facing summary of how to resolve this issue based on the knowledge above. Focus on the key steps and any important details. Do not include greetings or filler."""


def _generate_adapted_summary(
    customer_issue: str,
    top_content: str,
    top_source_type: str,
) -> str:
    """Generate a short LLM-adapted summary for the top suggestion."""
    from app.rag.core import LLM
    from app.rag.core.config import settings

    llm = LLM(model=settings.openai_planning_model)
    prompt = _ADAPT_SUMMARY_PROMPT.format(
        customer_issue=customer_issue[:500],
        source_type=top_source_type,
        content=top_content[:1500],
    )
    return llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )


def _build_score_breakdown(hit, blended_score: float) -> ScoreBreakdown:
    """Compute a ScoreBreakdown for a CorpusHit."""
    from datetime import datetime, timezone

    from app.rag.agent.nodes import _compute_learning_score
    from app.rag.core.config import settings

    learning_score = _compute_learning_score(hit)
    w = settings.confidence_blend_weight

    # Back-derive raw Cohere rerank score from the blended value
    divisor = 1.0 - w + w * learning_score
    raw_rerank = blended_score / divisor if divisor > 0 else blended_score

    # Compute freshness independently (same formula as nodes.py)
    freshness = 0.75
    if hit.updated_at:
        try:
            if isinstance(hit.updated_at, str):
                updated = datetime.fromisoformat(hit.updated_at.replace("Z", "+00:00"))
            else:
                updated = hit.updated_at
            days_old = (datetime.now(timezone.utc) - updated).days
            freshness = max(0.5, 1.0 - days_old / settings.freshness_half_life_days)
        except (ValueError, TypeError):
            pass

    return ScoreBreakdown(
        vector_similarity=round(hit.similarity, 4),
        rerank_score=round(raw_rerank, 4),
        confidence=round(hit.confidence if hit.confidence is not None else 0.5, 4),
        usage_count=hit.usage_count or 0,
        freshness=round(freshness, 4),
        learning_score=round(learning_score, 4),
        final_score=round(blended_score, 4),
    )


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


@router.post("/conversations/{conversation_id}/suggested-actions", response_model=List[SuggestedAction])
async def get_suggested_actions(
    conversation_id: str = Path(min_length=1, max_length=50),
    body: SuggestedActionsRequest = SuggestedActionsRequest(),
):
    """Retrieve AI-generated suggested actions for resolving a conversation.

    Uses RAG to search the retrieval_corpus (scripts, KB articles, ticket
    resolutions) based on the conversation context and returns the top hits
    as suggested actions for the support agent.

    Accepts optional live messages (from the frontend chat state) so the
    query reflects the full conversation, not just the initial seed messages.
    Also accepts exclude_ids to filter out previously used suggestions.

    Falls back to mock suggestions if RAG is unavailable.
    """
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = MOCK_CONVERSATIONS[conversation_id]

    # Build query from conversation context.
    # Prefer live messages from the request body; fall back to static seed.
    query_parts = [conversation.subject]
    if body.messages:
        for msg in reversed(body.messages):
            if msg.sender == "customer":
                query_parts.append(msg.content[:300])
                break
    else:
        seed_messages = MOCK_MESSAGES.get(conversation_id, [])
        for msg in reversed(seed_messages):
            if msg.sender == "customer":
                query_parts.append(msg.content[:300])
                break
    query = ". ".join(query_parts)

    exclude_set = set(body.exclude_ids)

    try:
        from app.rag.agent.graph import run_rag_retrieval_only

        # Request extra candidates so we still have enough after excluding
        fetch_k = 3 + len(exclude_set)
        result = await asyncio.to_thread(
            run_rag_retrieval_only,
            question=query,
            category=getattr(conversation, "category", None),
            top_k=fetch_k,
            conversation_id=conversation_id,
        )

        actions: list[SuggestedAction] = []
        for hit in result.top_hits:
            if hit.source_id in exclude_set:
                continue
            action_type = _SOURCE_TYPE_MAP.get(hit.source_type, "action")
            score = hit.rerank_score if hit.rerank_score is not None else hit.similarity
            breakdown = _build_score_breakdown(hit, score)
            actions.append(SuggestedAction(
                id=hit.source_id,
                type=action_type,
                confidence_score=round(score, 2),
                title=hit.title or hit.source_id,
                description=hit.content[:200] +
                "..." if len(hit.content) > 200 else hit.content,
                content=hit.content,
                source=f"{hit.source_type}: {hit.source_id}",
                score_breakdown=breakdown,
            ))
            if len(actions) >= 3:
                break

        if not actions:
            return MOCK_SUGGESTIONS

        # Generate adapted summaries for ALL suggestions in parallel
        async def _adapt(action: SuggestedAction) -> SuggestedAction:
            try:
                adapted = await asyncio.to_thread(
                    _generate_adapted_summary,
                    customer_issue=query,
                    top_content=action.content,
                    top_source_type=action.source,
                )
                return action.model_copy(update={"adapted_summary": adapted})
            except Exception:
                logger.exception("Failed to adapt suggestion %s", action.id)
                return action

        actions = list(await asyncio.gather(*[_adapt(a) for a in actions]))

        return actions

    except Exception:
        logger.exception(
            "RAG failed for conversation %s, falling back to mock", conversation_id)
        return MOCK_SUGGESTIONS


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
                customer_name=conversation.customer_name,
            )
            # Clear any LLM-generated ticket_number — only the DB-assigned one matters
            ticket.ticket_number = None

            logger.info("Generated ticket for conversation %s",
                        conversation_id)

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
                logger.exception(
                    "Failed to save ticket to DB for conversation %s", conversation_id)
                warnings.append(
                    "Ticket was generated but could not be saved to the database.")

        except Exception:
            logger.exception(
                "Failed to generate ticket for conversation %s", conversation_id)

    # Update conversation status in mock data
    MOCK_CONVERSATIONS[conversation_id] = conversation.model_copy(
        update={"status": "Resolved"})

    # Run self-learning pipeline only if ticket was saved to DB
    ticket_saved = ticket is not None and ticket.ticket_number is not None
    if ticket_saved and payload.resolution_type == "Resolved Successfully":
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
            logger.exception(
                "Learning pipeline failed for conversation %s", conversation_id)

    return CloseConversationResponse(
        status="success",
        message=f"Conversation {conversation_id} closed successfully",
        ticket=ticket,
        learning_result=learning_result,
        warnings=warnings,
    )


# ── Customer simulation endpoint ─────────────────────────────────────

_CUSTOMER_SIM_PROMPT = """You are simulating a customer in a support chat. You are {customer_name} with this issue: "{subject}".

Based on the conversation so far, respond naturally as the customer would.

Rules:
- If the agent's latest response contains a clear, actionable solution, there is roughly a 70% chance you accept it and say the issue is resolved. Otherwise ask a follow-up or say it didn't work.
- If the agent asks a clarifying question, answer it with plausible details.
- If the agent's response is vague or doesn't address your issue, push back politely.
- Keep responses concise (1-3 sentences).
- Stay in character — don't mention AI or simulation.

Respond with JSON: {{"content": "your reply", "resolved": true/false}}"""


@router.post(
    "/conversations/{conversation_id}/simulate-customer",
    response_model=SimulateCustomerResponse,
)
async def simulate_customer(
    conversation_id: str = Path(min_length=1, max_length=50),
    body: SimulateCustomerRequest = ...,
):
    """Generate a simulated customer reply using an LLM."""
    if conversation_id not in MOCK_CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = MOCK_CONVERSATIONS[conversation_id]

    system_prompt = _CUSTOMER_SIM_PROMPT.format(
        customer_name=conversation.customer_name,
        subject=conversation.subject,
    )

    chat_messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    for msg in body.messages:
        role = "assistant" if msg.sender == "customer" else "user"
        chat_messages.append({"role": role, "content": msg.content})

    try:
        from app.rag.core import LLM
        from app.rag.core.config import settings

        llm = LLM(model=settings.openai_planning_model)
        result: SimulateCustomerResponse = await asyncio.to_thread(
            llm.chat,
            messages=chat_messages,
            response_model=SimulateCustomerResponse,
            temperature=0.8,
        )
        return result
    except Exception:
        logger.exception("Customer simulation failed for %s", conversation_id)
        raise HTTPException(status_code=500, detail="Customer simulation failed")
