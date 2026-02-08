"""Mock suggested actions data.

Template placeholders used in scripts/responses:
- {{conversation_id}} - Current conversation ID
- {{customer_name}} - Customer's name
- {{property_id}} - Property ID (derived from conversation)
- {{ticket_subject}} - Conversation subject
- {{current_date}} - Today's date
- {{agent_name}} - Current agent name (placeholder)
"""

MOCK_SUGGESTIONS = [
    {
        "id": "act_8821_a",
        "type": "script",
        "confidence_score": 0.98,
        "title": "Fix Certifications Script",
        "description": "Updates the user settings table to force a refresh of the property certification status for {{customer_name}}.",
        "content": "-- Fix certification sync for {{customer_name}}\n-- Conversation: {{conversation_id}}\n-- Date: {{current_date}}\n\nUPDATE settings \nSET cert_status = 'pending_review' \nWHERE property_id = '{{property_id}}';",
        "source": "Ticket #9942",
    },
    {
        "id": "act_8821_b",
        "type": "response",
        "confidence_score": 0.85,
        "title": "Explain Compliance Delay",
        "description": "Knowledge base article explaining compliance delay causes and resolution steps.",
        "content": "Hi {{customer_name}},\n\nThank you for reaching out about the certification issue.\n\n**Issue Summary:**\nCustomers may experience delays in property certification syncing due to high load on the verification server. This typically manifests as a 505 error on the certifications page.\n\n**Resolution Steps:**\n1. I've verified your property ID ({{property_id}})\n2. I've checked the sync status in our admin panel\n3. If showing 'Pending', please allow 2-4 hours for the sync to complete\n4. If showing 'Error', I can run a fix script immediately\n\nPlease let me know if you'd like me to proceed with the fix.\n\nBest regards",
        "source": "Knowledge Base Art. 12",
    },
]

