"""Mock suggested actions data."""

MOCK_SUGGESTIONS = [
    {
        "id": "act_8821_a",
        "type": "script",
        "confidence_score": 0.98,
        "title": "Fix Certifications Script",
        "description": "Updates the user settings table to force a refresh of the property certification status.",
        "content": "UPDATE settings \nSET cert_status = 'pending_review' \nWHERE property_id = 'prop-8821';",
        "source": "Ticket #9942",
    },
    {
        "id": "act_8821_b",
        "type": "response",
        "confidence_score": 0.85,
        "title": "Explain Compliance Delay",
        "description": "Knowledge base article explaining compliance delay causes and resolution steps.",
        "content": 'Knowledge Base Article: Compliance Delays\\n\\nIssue: Customers may experience delays in property certification syncing due to high load on the verification server. This typically manifests as a 505 error on the certifications page.\\n\\nResolution Steps:\\n1. Verify the property ID.\\n2. Check the sync status in the admin panel.\\n3. If \'Pending\', advise the customer to wait 2-4 hours.\\n4. If \'Error\', run the \'Fix Certifications Script\'.',
        "source": "Knowledge Base Art. 12",
    },
]
