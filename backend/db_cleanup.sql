-- Run this in Supabase SQL Editor to fix constraint issues.
-- These are one-time migrations.

-- 1. Drop tickets -> conversations FK
-- The ticket_service no longer needs to create a conversations row just to satisfy this FK.
ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_ticket_number_fkey;

-- 2. Drop category FKs on knowledge_articles and retrieval_corpus
-- LLM-generated categories won't always match the categories reference table.
ALTER TABLE knowledge_articles DROP CONSTRAINT IF EXISTS knowledge_articles_category_fkey;
ALTER TABLE retrieval_corpus DROP CONSTRAINT IF EXISTS retrieval_corpus_category_fkey;

-- 3. Allow 'System' as a reviewer_role on learning_events
-- Auto-approved CONFIRMED events use reviewer_role = 'System'.
ALTER TABLE learning_events DROP CONSTRAINT IF EXISTS learning_events_reviewer_role_check;
ALTER TABLE learning_events ADD CONSTRAINT learning_events_reviewer_role_check
  CHECK (reviewer_role IN ('Tier 3 Support', 'Support Ops Review', 'System'));
