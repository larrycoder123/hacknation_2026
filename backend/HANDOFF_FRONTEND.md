# Frontend Changes Needed for Learning Pipeline Integration

## 1. Suggested Actions (existing, now RAG-powered)

The existing `GET /api/conversations/{id}/suggested-actions` endpoint is now powered by RAG instead of mock data. **No frontend changes needed** — the response format is identical.

The backend automatically:
1. Extracts context from the conversation (subject + last customer message)
2. Runs RAG to search scripts, KB articles, and ticket resolutions
3. Maps the top hits to `SuggestedAction[]` format

```
GET /api/conversations/{conversation_id}/suggested-actions

Response (unchanged format):
[
  {
    "id": "SCRIPT-0293",
    "type": "script",                    // "script" | "response" | "action"
    "confidence_score": 0.95,
    "title": "Date Advance Fix Script",
    "description": "Run this backend data-fix script to resolve...",
    "content": "use <DATABASE>\ngo\n\nupdate ...",
    "source": "SCRIPT: SCRIPT-0293"
  },
  {
    "id": "KB-3FFBFE3C70",
    "type": "response",
    "confidence_score": 0.82,
    "title": "Advance Property Date Troubleshooting",
    "description": "Steps to resolve property date sync issues...",
    "content": "...",
    "source": "KB: KB-3FFBFE3C70"
  }
]
```

Type mapping: `SCRIPT` → `"script"`, `KB` → `"response"`, `TICKET_RESOLUTION` → `"action"`

Falls back to mock suggestions if RAG is unavailable.

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
3. Ticket is saved to the database (ticket_number assigned)
4. All retrieval_log entries for this ticket get bulk-set to RESOLVED or UNHELPFUL (based on resolution_type)
5. Learning pipeline runs synchronously:
   - Stage 1: Updates confidence on corpus entries based on outcomes
   - Stage 2: Fresh RAG search using the ticket's resolution as query
   - Stage 3: Classifies as SAME_KNOWLEDGE / CONTRADICTS / NEW_KNOWLEDGE and acts

```
Response (extended):
{
  "status": "success",
  "message": "Conversation conv-123 closed successfully",
  "ticket": {
    "ticket_number": "CS-A1B2C3D4",
    "subject": "Unable to advance property date",
    "description": "...",
    "resolution": "Applied backend data-fix script...",
    "tags": ["date-advance", "backend-fix"],
    "category": "Advance Property Date",
    ...
  },
  "warnings": [],
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

**New fields in response:**
- `ticket.ticket_number` — DB-assigned ID (e.g. `CS-A1B2C3D4`)
- `warnings` — array of warning strings (e.g. DB save failures). Show as warning toasts if non-empty.
- `learning_result` — result of the self-learning pipeline (null if skipped or failed)

**Frontend needs:** After close, show a toast/banner based on `gap_classification`:
- `SAME_KNOWLEDGE` — "Knowledge confirmed - existing article boosted"
- `NEW_KNOWLEDGE` — "Knowledge gap detected - new KB article drafted for review"
- `CONTRADICTS` — "Contradiction detected - existing KB flagged for review"

If `learning_result` is null, the learning pipeline was skipped or failed.

---

### 2a. Exact TypeScript Changes

#### `frontend/app/types.ts` — Add missing types and update existing ones

**Add `ticket_number` to `Ticket` interface (line 56):**

```typescript
export interface Ticket {
  ticket_number?: string;        // ← ADD: DB-assigned ID (e.g. "CS-A1B2C3D4")
  subject: string;
  description: string;
  resolution: string;
  tags: string[];
  category?: string;
  related_error_codes?: string[];
  steps_to_reproduce?: string;
  resolution_steps?: string[];
  internal_notes?: string;
}
```

**Add new interfaces (after `CloseConversationResponse`, line 72):**

```typescript
export interface ConfidenceUpdate {
  source_type: string;
  source_id: string;
  delta: number;
  new_confidence: number;
  new_usage_count: number;
}

export type GapClassification = 'SAME_KNOWLEDGE' | 'CONTRADICTS' | 'NEW_KNOWLEDGE';

export interface SelfLearningResult {
  ticket_number: string;
  retrieval_logs_processed: number;
  confidence_updates: ConfidenceUpdate[];
  gap_classification?: GapClassification;
  matched_kb_article_id?: string;
  match_similarity?: number;
  learning_event_id?: string;
  drafted_kb_article_id?: string;
}
```

**Update `CloseConversationResponse` (line 68):**

```typescript
export interface CloseConversationResponse {
  status: string;
  message: string;
  ticket?: Ticket;
  warnings: string[];                        // ← ADD
  learning_result?: SelfLearningResult;      // ← ADD
}
```

#### `frontend/app/page.tsx` — Update `handleCloseConversation` (line 128)

The current code at **line 158-162** only logs the ticket to console:

```typescript
// Current (line 158-162):
if (response.ticket) {
  console.log("Ticket generated:", response.ticket);
  // You could show a toast or modal here to display the ticket
}
```

**Replace with:**

```typescript
// Show ticket number
if (response.ticket?.ticket_number) {
  const ticketMsg: Message = {
    id: `sys-ticket-${Date.now()}`,
    conversation_id: selectedConversationId,
    sender: "system",
    content: `Ticket created: ${response.ticket.ticket_number}`,
    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  };
  setMessages((prev) => ({
    ...prev,
    [selectedConversationId]: [...(prev[selectedConversationId] || []), ticketMsg],
  }));
}

// Show learning result
if (response.learning_result?.gap_classification) {
  const classificationMessages: Record<string, string> = {
    SAME_KNOWLEDGE: "Knowledge confirmed — existing article boosted",
    NEW_KNOWLEDGE: "Knowledge gap detected — new KB article drafted for review",
    CONTRADICTS: "Contradiction detected — existing KB flagged for review",
  };
  const learningMsg: Message = {
    id: `sys-learn-${Date.now()}`,
    conversation_id: selectedConversationId,
    sender: "system",
    content: classificationMessages[response.learning_result.gap_classification]
      || "Learning pipeline completed",
    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  };
  setMessages((prev) => ({
    ...prev,
    [selectedConversationId]: [...(prev[selectedConversationId] || []), learningMsg],
  }));
}

// Show warnings
if (response.warnings?.length) {
  response.warnings.forEach((w) => console.warn("Close warning:", w));
  // Optionally set error banner: setError(response.warnings.join("; "));
}
```

**Note:** The app uses an inline error banner pattern (see `page.tsx:171-176`) — there's no toast library installed. The simplest approach is to show feedback as system messages in the chat, as shown above. Alternatively, install a toast library (e.g. `sonner` or `react-hot-toast`) for non-intrusive notifications.

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
| `/api/conversations/{id}/suggested-actions` | GET | MODIFIED (same format) | Now RAG-powered instead of mock data |
| `/api/conversations/{id}/close` | POST | MODIFIED | Now saves ticket to DB, runs learning pipeline, returns `learning_result` + `warnings` |
| `/api/tickets/{id}/learn` | POST | EXISTS | Manual learning trigger (kept for testing) |
| `/api/learning-events/{id}/review` | POST | EXISTS | Approve/reject drafted KB |
