import {
    SuggestedAction,
    CloseConversationPayload,
    CloseConversationResponse,
    Conversation,
    Message
} from '../types';

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
