import { Ticket, Message, SuggestedAction } from './types';

export const MOCK_TICKETS: Ticket[] = [
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
    {
        id: '1026',
        customerName: 'Charlie Brown',
        subject: 'Feature request: Dark mode',
        priority: 'Low',
        status: 'Pending',
        timeAgo: '1h',
        lastMessage: 'Any updates on dark mode support?',
    },
    {
        id: '1027',
        customerName: 'Diana Prince',
        subject: 'Login issues on mobile',
        priority: 'High',
        status: 'Open',
        timeAgo: '2h',
        lastMessage: 'The app crashes when I try to log in.',
    },
    {
        id: '1028',
        customerName: 'Evan Wright',
        subject: 'Where can I find the API key?',
        priority: 'Medium',
        status: 'Resolved',
        timeAgo: '1d',
        lastMessage: 'Found it, thanks!',
    },
];

export const MOCK_MESSAGES: Record<string, Message[]> = {
    '1024': [
        {
            id: 'm1',
            ticketId: '1024',
            sender: 'customer',
            content: 'Hi, I am trying to access the property certifications for my new listing, but I keep getting an Error 505 page.',
            timestamp: '10:30 AM',
        },
        {
            id: 'm2',
            ticketId: '1024',
            sender: 'agent',
            content: 'Hello Alice, I can help you with that. Let me checks your account details.',
            timestamp: '10:32 AM',
        },
        {
            id: 'm3',
            ticketId: '1024',
            sender: 'customer',
            content: 'Okay, thanks. It is for property ID prop-8821.',
            timestamp: '10:33 AM',
        },
    ],
    '1025': [
        {
            id: 'm4',
            ticketId: '1025',
            sender: 'customer',
            content: 'I see two charges for March on my statement. Can you explain?',
            timestamp: '10:15 AM',
        },
    ],
};

export const MOCK_SUGGESTIONS: SuggestedAction[] = [
    {
        id: "act_8821_a",
        type: "script",
        confidence_score: 0.98,
        title: "Fix Certifications Script",
        description: "Updates the user settings table to force a refresh of the property certification status.",
        content: "UPDATE settings \nSET cert_status = 'pending_review' \nWHERE property_id = 'prop-8821';",
        source: "Ticket #9942"
    },
    {
        id: "act_8821_b",
        type: "response",
        confidence_score: 0.85,
        title: "Explain Compliance Delay",
        description: "Standard apology template for compliance delays.",
        content: `Knowledge Base Article: Compliance Delays

Issue: Customers may experience delays in property certification syncing due to high load on the verification server. This typically manifests as a 505 error on the certifications page.

Resolution Steps:
1. Verify the property ID.
2. Check the sync status in the admin panel.
3. If 'Pending', advise the customer to wait 2-4 hours.
4. If 'Error', run the 'Fix Certifications Script'.

Customer Communication Template:
"I apologize for the inconvenience. It appears our certification verification system is currently under heavy load, which is causing a delay in syncing your property details. This usually resolves within 2-4 hours. However, since you are seeing an error, I can manually trigger a refresh for you. Would you like me to do that now?"`,
        source: "Knowledge Base Art. 12"
    },
    {
        id: "act_8821_c",
        type: "action",
        confidence_score: 0.45,
        title: "Escalate to Engineering",
        description: "If the script fails, escalate immediately.",
        content: "ESCALATE_TICKET",
        source: "SOP Rule #4"
    }
];
