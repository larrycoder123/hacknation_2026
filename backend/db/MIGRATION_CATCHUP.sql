-- =============================================================================
-- SupportMind: Migration Catchup
-- =============================================================================
-- Run this if you already applied migrations 001-004 + db_cleanup.sql
-- but have NOT yet applied the HANDOFF_DATABASE.md changes.
--
-- These are the remaining changes needed to match what the code expects.
-- All statements are idempotent (safe to re-run).
-- =============================================================================

-- ─── 1. learning_events: add event_type column ─────────────────────────

-- Classifies the event: GAP (new knowledge), CONTRADICTION (outdated KB),
-- CONFIRMED (existing knowledge validated)
DO $$ BEGIN
    ALTER TABLE learning_events ADD COLUMN event_type TEXT
        CHECK (event_type IN ('GAP', 'CONTRADICTION', 'CONFIRMED'));
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Backfill existing rows: all current learning events are GAP type
UPDATE learning_events
SET event_type = 'GAP'
WHERE proposed_kb_article_id IS NOT NULL AND event_type IS NULL;

-- ─── 2. learning_events: add flagged_kb_article_id column ──────────────

-- For CONTRADICTION events: which existing KB article is being contradicted
DO $$ BEGIN
    ALTER TABLE learning_events ADD COLUMN flagged_kb_article_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Index for event_type queries
CREATE INDEX IF NOT EXISTS idx_learning_event_type ON learning_events (event_type);

-- ─── 3. retrieval_log: make ticket_number nullable ─────────────────────

-- During live support, RAG logs are created with conversation_id only.
-- ticket_number gets stamped when the conversation closes.
ALTER TABLE retrieval_log ALTER COLUMN ticket_number DROP NOT NULL;

-- ─── 4. retrieval_log: drop FK on ticket_number ────────────────────────

-- Logs exist before the ticket is created in the DB
ALTER TABLE retrieval_log DROP CONSTRAINT IF EXISTS retrieval_log_ticket_number_fkey;

-- ─── 5. retrieval_log: add conversation_id column ──────────────────────

DO $$ BEGIN
    ALTER TABLE retrieval_log ADD COLUMN conversation_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_retrieval_log_conversation ON retrieval_log (conversation_id);

-- ─── 6. retrieval_log: drop unique constraint ──────────────────────────

-- Multiple RAG calls per conversation are allowed
ALTER TABLE retrieval_log DROP CONSTRAINT IF EXISTS retrieval_log_ticket_number_attempt_number_key;

-- ─── 7. retrieval_log: add created_at index ────────────────────────────

CREATE INDEX IF NOT EXISTS idx_retrieval_log_created ON retrieval_log (created_at DESC);

-- ═══════════════════════════════════════════════════════════════════════
-- VERIFY: Run these queries to confirm everything is in place
-- ═══════════════════════════════════════════════════════════════════════

-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'learning_events'
-- ORDER BY ordinal_position;

-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'retrieval_log'
-- ORDER BY ordinal_position;
