import {
    SuggestedAction,
    CloseTicketPayload,
    CloseTicketResponse,
    Ticket,
    Message
} from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

/**
 * Fetch all tickets from the backend.
 */
export async function fetchTickets(): Promise<Ticket[]> {
    const response = await fetch(`${API_BASE_URL}/tickets`);
    if (!response.ok) {
        throw new Error('Failed to fetch tickets');
    }
    return response.json();
}

/**
 * Fetch a single ticket by ID.
 */
export async function fetchTicket(ticketId: string): Promise<Ticket> {
    const response = await fetch(`${API_BASE_URL}/tickets/${ticketId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch ticket');
    }
    return response.json();
}

/**
 * Fetch all messages for a ticket.
 */
export async function fetchTicketMessages(ticketId: string): Promise<Message[]> {
    const response = await fetch(`${API_BASE_URL}/tickets/${ticketId}/messages`);
    if (!response.ok) {
        throw new Error('Failed to fetch messages');
    }
    return response.json();
}

/**
 * Fetch AI-suggested actions for a ticket.
 */
export async function fetchSuggestedActions(ticketId: string): Promise<SuggestedAction[]> {
    const response = await fetch(`${API_BASE_URL}/tickets/${ticketId}/suggested-actions`);
    if (!response.ok) {
        throw new Error('Failed to fetch suggested actions');
    }
    return response.json();
}

/**
 * Close a ticket and optionally generate a knowledge article.
 */
export async function closeTicket(payload: CloseTicketPayload): Promise<CloseTicketResponse> {
    const response = await fetch(`${API_BASE_URL}/tickets/${payload.ticket_id}/close`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        throw new Error('Failed to close ticket');
    }

    return response.json();
}
