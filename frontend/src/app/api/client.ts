import {
    SuggestedAction,
    CloseConversationPayload,
    CloseConversationResponse,
    Conversation,
    Message,
    LearningEventListResponse,
    ReviewDecisionPayload,
    LearningEventDetail,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

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
 */
export async function fetchSuggestedActions(conversationId: string): Promise<SuggestedAction[]> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/suggested-actions`);
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
