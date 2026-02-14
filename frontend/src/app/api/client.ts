import {
    SuggestedAction,
    CloseConversationPayload,
    CloseConversationResponse,
    SelfLearningResult,
    Conversation,
    Message,
    SimulateCustomerResponse,
    LearningEventListResponse,
    ReviewDecisionPayload,
    LearningEventDetail,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

/**
 * Ping the backend root to check if the server is awake.
 * Strips `/api` from API_BASE_URL to hit `GET /`.
 */
export async function checkBackendHealth(): Promise<boolean> {
    const baseUrl = API_BASE_URL.replace(/\/api\/?$/, '');
    try {
        const response = await fetch(baseUrl, { signal: AbortSignal.timeout(5_000) });
        return response.ok;
    } catch {
        return false;
    }
}

/**
 * Fetch all conversations from the backend.
 */
export async function fetchConversations(): Promise<Conversation[]> {
    const response = await fetch(`${API_BASE_URL}/conversations`);
    if (!response.ok) {
        throw new Error('Failed to fetch conversations');
    }
    return response.json();
}

/**
 * Fetch a single conversation by ID.
 */
export async function fetchConversation(conversationId: string): Promise<Conversation> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch conversation');
    }
    return response.json();
}

/**
 * Fetch all messages for a conversation.
 */
export async function fetchConversationMessages(conversationId: string): Promise<Message[]> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`);
    if (!response.ok) {
        throw new Error('Failed to fetch messages');
    }
    return response.json();
}

/**
 * Fetch AI-suggested actions for a conversation.
 * Sends live messages so RAG queries reflect the full conversation,
 * and exclude_ids to filter out already-used suggestions.
 */
export async function fetchSuggestedActions(
    conversationId: string,
    messages?: { sender: 'agent' | 'customer'; content: string }[],
    excludeIds?: string[],
): Promise<SuggestedAction[]> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/suggested-actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            messages: messages || [],
            exclude_ids: excludeIds || [],
        }),
    });
    if (!response.ok) {
        throw new Error('Failed to fetch suggested actions');
    }
    return response.json();
}

/**
 * Close a conversation and optionally generate a ticket.
 */
export async function closeConversation(payload: CloseConversationPayload): Promise<CloseConversationResponse> {
    const response = await fetch(`${API_BASE_URL}/conversations/${payload.conversation_id}/close`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        throw new Error('Failed to close conversation');
    }

    return response.json();
}

/**
 * Run the self-learning pipeline for a ticket (Stages 1-3: confidence updates + gap detection).
 * Called after close endpoint has already set outcomes (Stage 0).
 */
export async function runLearningPipeline(ticketNumber: string): Promise<SelfLearningResult> {
    const response = await fetch(`${API_BASE_URL}/tickets/${ticketNumber}/learn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
        throw new Error('Learning pipeline failed');
    }
    return response.json();
}

/**
 * Fetch learning events with optional filters.
 */
export async function fetchLearningEvents(params?: {
    status?: string;
    event_type?: string;
    limit?: number;
    offset?: number;
}): Promise<LearningEventListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.event_type) searchParams.set('event_type', params.event_type);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));

    const qs = searchParams.toString();
    const response = await fetch(`${API_BASE_URL}/learning-events${qs ? `?${qs}` : ''}`);
    if (!response.ok) {
        throw new Error('Failed to fetch learning events');
    }
    return response.json();
}

/**
 * Approve or reject a learning event.
 */
export async function reviewLearningEvent(
    eventId: string,
    payload: ReviewDecisionPayload,
): Promise<LearningEventDetail> {
    const response = await fetch(`${API_BASE_URL}/learning-events/${eventId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error('Failed to review learning event');
    }
    return response.json();
}

/**
 * Simulate a customer reply using an LLM.
 */
export async function simulateCustomerReply(
    conversationId: string,
    messages: { sender: 'agent' | 'customer'; content: string }[],
): Promise<SimulateCustomerResponse> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/simulate-customer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
    });
    if (!response.ok) {
        throw new Error('Failed to simulate customer reply');
    }
    return response.json();
}
