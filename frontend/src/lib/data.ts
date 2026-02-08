/**
 * This file is kept for reference purposes only.
 * The application now fetches data from the backend API.
 * See app/api/client.ts for the API client implementation.
 */

import { ConversationDisplay, Message, SuggestedAction } from '@/types';

// Legacy mock data - not used in production
// The backend now serves this data via the API endpoints

export const MOCK_CONVERSATIONS: ConversationDisplay[] = [
    {
        id: '1024',
        customerName: 'Alice Johnson',
        subject: 'Cannot access property certifications',
        priority: 'High',
        status: 'Open',
        timeAgo: '5m',
        lastMessage: 'I am getting Error 505 when trying to view certificates.',
    },
    {
        id: '1025',
        customerName: 'Bob Smith',
        subject: 'Billing question for March',
        priority: 'Medium',
        status: 'Open',
        timeAgo: '12m',
        lastMessage: 'Why was I charged twice?',
    },
];

export const MOCK_MESSAGES: Record<string, Message[]> = {
    '1024': [
        {
            id: 'm1',
            conversation_id: '1024',
            sender: 'customer',
            content: 'Hi, I am trying to access the property certifications.',
            timestamp: '10:30 AM',
        },
    ],
};

export const MOCK_SUGGESTIONS: SuggestedAction[] = [
    {
        id: "act_8821_a",
        type: "script",
        confidence_score: 0.98,
        title: "Fix Certifications Script",
        description: "Updates the user settings table.",
        content: "UPDATE settings SET cert_status = 'pending_review';",
        source: "Ticket #9942"
    },
];
