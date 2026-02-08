# Database Schema Changes for Learning Pipeline

## 1. Modify `learning_events` table

Add two new columns:

```sql
-- New column: event type classification
ALTER TABLE learning_events
ADD COLUMN event_type TEXT CHECK (event_type IN ('GAP', 'CONTRADICTION', 'CONFIRMED'));

-- New column: existing KB article that contradicts (for CONTRADICTION events)
ALTER TABLE learning_events
ADD COLUMN flagged_kb_article_id TEXT;

-- Update existing rows (all current events are GAP type)
UPDATE learning_events
SET event_type = 'GAP'
WHERE proposed_kb_article_id IS NOT NULL AND event_type IS NULL;
```

### Updated `learning_events` schema:

| Column | Type | Description |
|---|---|---|
| event_id | TEXT PK | e.g. `LE-abc123def456` |
| trigger_ticket_number | TEXT FK | Ticket that triggered the event |
| detected_gap | TEXT | Description of what was detected |
| **event_type** | TEXT | **NEW**: `GAP`, `CONTRADICTION`, or `CONFIRMED` |
| proposed_kb_article_id | TEXT FK | Drafted KB article (GAP + CONTRADICTION) |
| **flagged_kb_article_id** | TEXT FK | **NEW**: Existing KB that contradicts (CONTRADICTION only) |
| draft_summary | TEXT | Summary of the draft |
| final_status | TEXT | `Approved`, `Rejected`, or auto-`Approved` for CONFIRMED |
| reviewer_role | TEXT | Who reviewed (`System` for auto-approved CONFIRMED events) |
| event_timestamp | TIMESTAMPTZ | When the event occurred |

## 2. Modify `retrieval_log` table

The table exists from the migration but needs changes for pre-ticket logging. During live support, the agent gets suggested actions via RAG before a ticket exists — those logs are linked by `conversation_id` and later stamped with `ticket_number` when the conversation closes.

```sql
-- Make ticket_number nullable (logs exist before ticket is created)
ALTER TABLE retrieval_log ALTER COLUMN ticket_number DROP NOT NULL;

-- Drop the FK constraint (conversation_id is used before ticket exists in DB)
ALTER TABLE retrieval_log DROP CONSTRAINT retrieval_log_ticket_number_fkey;

-- Add conversation_id column for pre-ticket log linking
ALTER TABLE retrieval_log ADD COLUMN conversation_id TEXT;
CREATE INDEX idx_retrieval_log_conversation ON retrieval_log(conversation_id);

-- Drop the unique constraint that conflicts with multiple RAG calls per conversation
ALTER TABLE retrieval_log DROP CONSTRAINT retrieval_log_ticket_number_attempt_number_key;
```

**How logging works:**
1. Agent opens conversation → views suggested actions → RAG logs with `conversation_id` only
2. Agent closes conversation → ticket created → backend runs: `UPDATE retrieval_log SET ticket_number = $1 WHERE conversation_id = $2 AND ticket_number IS NULL`
3. Learning pipeline reads logs by `ticket_number`, bulk-sets outcomes

**Note on outcomes:** Outcomes are NOT set per-answer. When a conversation closes, the backend bulk-updates all retrieval_log rows for that ticket:
- "Resolved Successfully" → all outcomes set to `RESOLVED`
- "Not Applicable" → all outcomes set to `UNHELPFUL`

## 3. Ensure `match_corpus()` RPC exists

See `backend/app/rag/db/rpc_functions.sql` for the full definition. This RPC is called by the RAG's retrieve node during both live support and gap detection.

## 4. Ensure `update_corpus_confidence` RPC exists

Called by the learning service to bump/drop confidence scores:

```sql
CREATE OR REPLACE FUNCTION update_corpus_confidence(
    p_source_type TEXT,
    p_source_id TEXT,
    p_delta FLOAT,
    p_increment_usage BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (new_confidence FLOAT, new_usage_count INT) AS $$
BEGIN
    RETURN QUERY
    UPDATE retrieval_corpus
    SET
        confidence = GREATEST(0.0, LEAST(1.0, confidence + p_delta)),
        usage_count = CASE WHEN p_increment_usage THEN usage_count + 1 ELSE usage_count END,
        updated_at = now()
    WHERE source_type = p_source_type AND source_id = p_source_id
    RETURNING confidence AS new_confidence, usage_count AS new_usage_count;
END;
$$ LANGUAGE plpgsql;
```

## Summary of Changes

| Object | Action | Notes |
|---|---|---|
| `learning_events.event_type` | ADD COLUMN | `GAP` / `CONTRADICTION` / `CONFIRMED` |
| `learning_events.flagged_kb_article_id` | ADD COLUMN | For CONTRADICTION events |
| `retrieval_log` | ALTER TABLE | Add `conversation_id`, make `ticket_number` nullable, drop FK + unique constraint |
| `match_corpus()` RPC | VERIFY EXISTS | Created by RAG rpc_functions.sql |
| `update_corpus_confidence()` RPC | VERIFY/CREATE | Used by learning service |
