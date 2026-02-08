import { SuggestedAction, CloseTicketPayload } from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

export async function fetchSuggestedActions(ticketId: string): Promise<SuggestedAction[]> {
    const response = await fetch(`${API_BASE_URL}/tickets/${ticketId}/suggested-actions`);
    if (!response.ok) {
        throw new Error('Failed to fetch suggested actions');
    }
    return response.json();
}

export async function closeTicket(payload: CloseTicketPayload): Promise<void> {
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
}
