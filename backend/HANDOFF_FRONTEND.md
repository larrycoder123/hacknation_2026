# Frontend Changes Needed for Learning Pipeline Integration

## 1. New Endpoint: Ask Copilot

The backend exposes a RAG-powered question answering endpoint for live support.

```
POST /api/conversations/{conversation_id}/ask
Content-Type: application/json

{
  "question": "How do I fix the property date sync issue?",
  "ticket_number": "CS-38908386"       // optional, for retrieval logging
}

Response:
{
  "answer": "To resolve the property date sync issue...",
  "citations": [
    {
      "source_type": "SCRIPT",
      "source_id": "SCRIPT-0293",
      "title": "Date Advance Fix Script",
      "quote": "Relevant excerpt..."
    }
  ],
  "confidence": "medium",
  "retrieval_queries": ["property date sync fix", ...]
}
```

**Frontend needs:** Replace the mock suggested-actions call with this endpoint. Show the answer + citations in the copilot panel.

No per-answer feedback is needed — outcomes are set automatically when the conversation closes.

## 2. Close Conversation (existing, response extended)

The existing `POST /api/conversations/{id}/close` payload and response:

```
Request (unchanged):
{
  "conversation_id": "conv-123",
  "resolution_type": "Resolved Successfully",   // or "Not Applicable"
  "notes": "Applied backend data-fix script...", // agent's resolution notes
  "create_ticket": true
}
```

**What happens on close:**
1. Agent provides resolution notes describing what they did
2. LLM generates a structured Ticket from conversation + notes
3. All retrieval_log entries for this ticket get bulk-set to RESOLVED or UNHELPFUL (based on resolution_type)
4. Learning pipeline runs synchronously:
   - Stage 1: Updates confidence on corpus entries based on outcomes
   - Stage 2: Fresh RAG search using the ticket's resolution as query
   - Stage 3: Classifies as SAME_KNOWLEDGE / CONTRADICTS / NEW_KNOWLEDGE and acts

```
Response (extended):
{
  "status": "success",
  "message": "Conversation conv-123 closed successfully",
  "ticket": {
    "subject": "Unable to advance property date",
    "description": "...",
    "resolution": "Applied backend data-fix script...",
    "tags": ["date-advance", "backend-fix"],
    "category": "Advance Property Date",
    ...
  },
  "learning_result": {
    "ticket_number": "CS-38908386",
    "retrieval_logs_processed": 3,
    "confidence_updates": [...],
    "gap_classification": "NEW_KNOWLEDGE",     // or "SAME_KNOWLEDGE" or "CONTRADICTS"
    "matched_kb_article_id": null,             // set for SAME/CONTRADICTS
    "match_similarity": null,
    "learning_event_id": "LE-abc123def456",
    "drafted_kb_article_id": "KB-SYN-A1B2C3D4"
  }
}
```

**Frontend needs:** After close, show a toast/banner based on `gap_classification`:
- `SAME_KNOWLEDGE` — "Knowledge confirmed - existing article boosted"
- `NEW_KNOWLEDGE` — "Knowledge gap detected - new KB article drafted for review"
- `CONTRADICTS` — "Contradiction detected - existing KB flagged for review"

If `learning_result` is null, the learning pipeline was skipped or failed.

## 3. Learning Events Review Dashboard

The review endpoint:

```
POST /api/learning-events/{event_id}/review
Content-Type: application/json

{
  "decision": "Approved",           // or "Rejected"
  "reviewer_role": "Tier 3 Support",
  "reason": "Looks good"            // optional
}
```

**Frontend needs:** A review dashboard page that:
- Lists pending learning_events (event_type = GAP or CONTRADICTION)
- For GAP: shows the drafted KB article, reviewer approves/rejects
- For CONTRADICTION: shows old KB article vs new draft side-by-side, reviewer approves replacement or rejects
- CONFIRMED events (SAME_KNOWLEDGE) can be shown in a separate "audit log" tab but don't need review

## 4. Endpoints Summary

| Endpoint | Method | Status | Purpose |
|---|---|---|---|
| `/api/conversations/{id}/ask` | POST | NEW | RAG-powered copilot answers |
| `/api/conversations/{id}/close` | POST | MODIFIED | Now runs learning pipeline, returns `learning_result` |
| `/api/tickets/{id}/learn` | POST | EXISTS | Manual learning trigger (kept for testing) |
| `/api/learning-events/{id}/review` | POST | EXISTS | Approve/reject drafted KB |
