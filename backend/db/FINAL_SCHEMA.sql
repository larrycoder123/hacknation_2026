-- =============================================================================
-- SupportMind: FINAL Database Schema
-- =============================================================================
-- This file represents the COMPLETE, CURRENT state of the database.
-- Run this on a FRESH Supabase project to set up everything from scratch.
-- If you already ran the migrations (001-004 + db_cleanup.sql), see
-- MIGRATION_CATCHUP.sql below for the remaining changes.
--
-- Tables: 12
-- RPC functions: 3
-- Indexes: 36+
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- ═══════════════════════════════════════════════════════════════════════
-- 1. LOOKUPS & CONFIG
-- ═══════════════════════════════════════════════════════════════════════

-- Issue categories shared across the system
CREATE TABLE categories (
    name TEXT PRIMARY KEY
);

-- What each <PLACEHOLDER> token means in scripts
CREATE TABLE placeholder_dictionary (
    placeholder TEXT PRIMARY KEY,
    meaning     TEXT,
    example     TEXT
);

-- App settings (thresholds, feature flags)
CREATE TABLE config (
    key   TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- ═══════════════════════════════════════════════════════════════════════
-- 2. CORE DOMAIN
-- ═══════════════════════════════════════════════════════════════════════

-- Tier 3 backend data-fix scripts (999 rows from dataset)
CREATE TABLE scripts_master (
    script_id             TEXT PRIMARY KEY,        -- SCRIPT-0001
    script_title          TEXT,
    script_purpose        TEXT,
    module                TEXT,
    category              TEXT REFERENCES categories (name),
    source                TEXT CHECK (source IN ('Questions', 'Tickets')),
    script_text_sanitized TEXT                     -- SQL with <PLACEHOLDER> tokens
);

-- KB articles: 3,046 seed + 161 synthetic from learning loop
-- NOTE: category FK to categories was DROPPED (LLM-generated categories
--       may not match the lookup table)
CREATE TABLE knowledge_articles (
    kb_article_id TEXT PRIMARY KEY,                -- seed: KB-{hex}, synthetic: KB-SYN-XXXX
    title         TEXT,
    body          TEXT,
    tags          TEXT,
    module        TEXT,
    category      TEXT,                            -- NO FK (dropped)
    created_at    TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ,
    status        TEXT DEFAULT 'Active' CHECK (status IN ('Active', 'Draft', 'Archived')),
    source_type   TEXT NOT NULL CHECK (source_type IN ('SEED_KB', 'SYNTH_FROM_TICKET'))
);

-- Agent/customer transcripts (400 populated out of 999 in dataset)
CREATE TABLE conversations (
    ticket_number            TEXT PRIMARY KEY,
    conversation_id          TEXT UNIQUE,
    channel                  TEXT CHECK (channel IN ('Chat', 'Phone') OR channel IS NULL),
    conversation_start       TIMESTAMPTZ,
    conversation_end         TIMESTAMPTZ,
    customer_role            TEXT,
    agent_name               TEXT,
    product                  TEXT,
    category                 TEXT REFERENCES categories (name),
    issue_summary            TEXT,
    transcript               TEXT,                 -- full Agent:/Customer: turns
    sentiment                TEXT CHECK (sentiment IN ('Neutral', 'Relieved', 'Curious', 'Frustrated') OR sentiment IS NULL),
    generation_source_record TEXT
);

-- ═══════════════════════════════════════════════════════════════════════
-- 3. JOINS & EXTENSIONS
-- ═══════════════════════════════════════════════════════════════════════

-- Which placeholders each script requires
CREATE TABLE script_placeholders (
    script_id   TEXT NOT NULL REFERENCES scripts_master (script_id),
    placeholder TEXT NOT NULL REFERENCES placeholder_dictionary (placeholder),
    PRIMARY KEY (script_id, placeholder)
);

-- Support cases, 1:1 with conversations via ticket_number
-- NOTE: ticket_number FK to conversations was DROPPED (ticket_service creates
--       tickets independently — the conversation may not exist in DB yet)
CREATE TABLE tickets (
    ticket_number           TEXT PRIMARY KEY,       -- NO FK to conversations (dropped)
    created_at              TIMESTAMPTZ,
    closed_at               TIMESTAMPTZ,
    status                  TEXT CHECK (status IN ('Open', 'Closed', 'Pending') OR status IS NULL),
    priority                TEXT CHECK (priority IN ('Critical', 'High', 'Medium', 'Low') OR priority IS NULL),
    tier                    TEXT CHECK (tier IN ('1', '2', '3') OR tier IS NULL),
    module                  TEXT,
    case_type               TEXT CHECK (case_type IN ('Incident', 'How-To', 'Training') OR case_type IS NULL),
    subject                 TEXT,
    description             TEXT,
    resolution              TEXT,
    root_cause              TEXT,
    tags                    TEXT,
    kb_article_id           TEXT REFERENCES knowledge_articles (kb_article_id),
    script_id               TEXT REFERENCES scripts_master (script_id),
    generated_kb_article_id TEXT REFERENCES knowledge_articles (kb_article_id)
);

-- ═══════════════════════════════════════════════════════════════════════
-- 4. WORKFLOW & AUDIT
-- ═══════════════════════════════════════════════════════════════════════

-- Provenance chain: synthetic KB → source ticket/conversation/script
-- Pattern: 3 rows per synthetic article (CREATED_FROM Ticket + Conversation, REFERENCES Script)
CREATE TABLE kb_lineage (
    kb_article_id    TEXT NOT NULL REFERENCES knowledge_articles (kb_article_id),
    source_type      TEXT NOT NULL CHECK (source_type IN ('Ticket', 'Conversation', 'Script')),
    source_id        TEXT NOT NULL,
    relationship     TEXT NOT NULL CHECK (relationship IN ('CREATED_FROM', 'REFERENCES')),
    evidence_snippet TEXT,
    event_timestamp  TIMESTAMPTZ,
    PRIMARY KEY (kb_article_id, source_type, source_id)
);

-- Learning loop audit: gap detected → KB drafted → human approves/rejects
-- Includes event_type classification and contradiction tracking
CREATE TABLE learning_events (
    event_id                TEXT PRIMARY KEY,       -- LE-{uuid} or LEARN-XXXX (dataset)
    trigger_ticket_number   TEXT REFERENCES tickets (ticket_number),
    detected_gap            TEXT,
    event_type              TEXT CHECK (event_type IN ('GAP', 'CONTRADICTION', 'CONFIRMED')),
    proposed_kb_article_id  TEXT REFERENCES knowledge_articles (kb_article_id),
    flagged_kb_article_id   TEXT,                   -- existing KB that contradicts (CONTRADICTION only)
    draft_summary           TEXT,
    final_status            TEXT CHECK (final_status IN ('Approved', 'Rejected') OR final_status IS NULL),
    reviewer_role           TEXT CHECK (reviewer_role IN ('Tier 3 Support', 'Support Ops Review', 'System') OR reviewer_role IS NULL),
    event_timestamp         TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════
-- 5. SEARCH & EVALUATION
-- ═══════════════════════════════════════════════════════════════════════

-- 1,000 ground-truth Q&A pairs for measuring retrieval accuracy (hit@k)
CREATE TABLE questions (
    question_id             TEXT PRIMARY KEY,       -- Q-0001
    source                  TEXT CHECK (source IN ('Scripts', 'AFF Data')),
    product                 TEXT,
    category                TEXT REFERENCES categories (name),
    module                  TEXT,
    difficulty              TEXT CHECK (difficulty IN ('Easy', 'Medium', 'Hard') OR difficulty IS NULL),
    question_text           TEXT,
    answer_type             TEXT CHECK (answer_type IN ('SCRIPT', 'KB', 'TICKET_RESOLUTION')),
    target_id               TEXT,                   -- FK to scripts_master / knowledge_articles / tickets
    target_title            TEXT,
    generation_source_record TEXT
);

-- Unified RAG vector space: all three answer sources in one table
-- Content composed from:
--   SCRIPT:            script_purpose + script_text_sanitized
--   KB:                body
--   TICKET_RESOLUTION: description + root_cause + resolution
-- Embedding model: text-embedding-3-large (3072 dimensions)
-- NOTE: category FK to categories was DROPPED
CREATE TABLE retrieval_corpus (
    source_type  TEXT NOT NULL CHECK (source_type IN ('SCRIPT', 'KB', 'TICKET_RESOLUTION')),
    source_id    TEXT NOT NULL,
    title        TEXT,
    content      TEXT,
    category     TEXT,                              -- NO FK (dropped)
    module       TEXT,
    tags         TEXT DEFAULT '',
    embedding    vector(3072),
    confidence   FLOAT NOT NULL DEFAULT 0.5,        -- feedback score [0.0, 1.0]
    usage_count  INT NOT NULL DEFAULT 0,            -- times used in a resolution
    updated_at   TIMESTAMPTZ DEFAULT now(),         -- content freshness
    PRIMARY KEY (source_type, source_id)
);

-- Per-attempt RAG search log. One row per retrieval attempt.
-- During live support: logged with conversation_id only (no ticket yet).
-- On close: ticket_number stamped, outcomes bulk-set.
CREATE TABLE retrieval_log (
    retrieval_id   TEXT PRIMARY KEY,                -- RET-{uuid}
    ticket_number  TEXT,                            -- nullable: linked after ticket creation
    conversation_id TEXT,                           -- set during live support
    attempt_number INT NOT NULL DEFAULT 1,
    query_text     TEXT,
    source_type    TEXT,                            -- matched corpus source_type (null if no match)
    source_id      TEXT,                            -- matched corpus source_id (null if no match)
    similarity_score FLOAT,
    outcome        TEXT CHECK (outcome IN ('RESOLVED', 'UNHELPFUL', 'PARTIAL') OR outcome IS NULL),
    execution_id   TEXT,                            -- links to rag_execution_log (gap detection runs)
    created_at     TIMESTAMPTZ DEFAULT now()
);
-- NOTE: no UNIQUE constraint on (ticket_number, attempt_number)
-- NOTE: no FK on ticket_number (logs exist before ticket is created)

-- Pipeline-level execution log. One row per RAG pipeline run (gap detection only).
-- Captures latency, token usage, and classification for observability.
-- Links to retrieval_log via execution_id for drill-down into individual hits.
CREATE TABLE rag_execution_log (
    execution_id    TEXT PRIMARY KEY,               -- EXEC-{uuid}
    graph_type      TEXT NOT NULL CHECK (graph_type IN ('QA', 'GAP_DETECTION')),
    conversation_id TEXT,
    ticket_number   TEXT,
    query           TEXT,
    total_latency_ms INT,
    node_latencies  JSONB,                          -- {"plan_query": 820, "retrieve": 1200, ...}
    tokens_input    INT DEFAULT 0,
    tokens_output   INT DEFAULT 0,
    evidence_count  INT DEFAULT 0,
    top_similarity  FLOAT,
    top_rerank_score FLOAT,
    classification  TEXT,                           -- GAP_DETECTION only: SAME_KNOWLEDGE / CONTRADICTS / NEW_KNOWLEDGE
    status          TEXT DEFAULT 'success',         -- success / error / insufficient_evidence
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════════════════

-- Tickets
CREATE INDEX idx_tickets_status          ON tickets (status);
CREATE INDEX idx_tickets_priority        ON tickets (priority);
CREATE INDEX idx_tickets_tier            ON tickets (tier);
CREATE INDEX idx_tickets_script_id       ON tickets (script_id);
CREATE INDEX idx_tickets_kb_article_id   ON tickets (kb_article_id);
CREATE INDEX idx_tickets_generated_kb    ON tickets (generated_kb_article_id);

-- Conversations
CREATE INDEX idx_conversations_category  ON conversations (category);
CREATE INDEX idx_conversations_channel   ON conversations (channel);
CREATE INDEX idx_conversations_sentiment ON conversations (sentiment);

-- KB articles
CREATE INDEX idx_kb_source_type          ON knowledge_articles (source_type);
CREATE INDEX idx_kb_category             ON knowledge_articles (category);
CREATE INDEX idx_kb_status               ON knowledge_articles (status);

-- KB lineage
CREATE INDEX idx_kb_lineage_source       ON kb_lineage (source_type, source_id);

-- Learning events
CREATE INDEX idx_learning_status         ON learning_events (final_status);
CREATE INDEX idx_learning_ticket         ON learning_events (trigger_ticket_number);
CREATE INDEX idx_learning_kb             ON learning_events (proposed_kb_article_id);
CREATE INDEX idx_learning_event_type     ON learning_events (event_type);

-- Questions
CREATE INDEX idx_questions_answer_type   ON questions (answer_type);
CREATE INDEX idx_questions_target_id     ON questions (target_id);
CREATE INDEX idx_questions_category      ON questions (category);
CREATE INDEX idx_questions_difficulty    ON questions (difficulty);

-- Scripts
CREATE INDEX idx_scripts_category        ON scripts_master (category);
CREATE INDEX idx_scripts_module          ON scripts_master (module);

-- Script placeholders
CREATE INDEX idx_script_placeholders_placeholder ON script_placeholders (placeholder);

-- Retrieval corpus: b-tree
CREATE INDEX idx_corpus_source_type      ON retrieval_corpus (source_type);
CREATE INDEX idx_corpus_category         ON retrieval_corpus (category);

-- Retrieval corpus: GIN full-text search
CREATE INDEX idx_corpus_content_fts ON retrieval_corpus
    USING gin (to_tsvector('english', coalesce(content, '')));
CREATE INDEX idx_corpus_title_fts ON retrieval_corpus
    USING gin (to_tsvector('english', coalesce(title, '')));

-- Retrieval log
CREATE INDEX idx_retrieval_log_ticket       ON retrieval_log (ticket_number);
CREATE INDEX idx_retrieval_log_conversation ON retrieval_log (conversation_id);
CREATE INDEX idx_retrieval_log_outcome      ON retrieval_log (outcome);
CREATE INDEX idx_retrieval_log_source       ON retrieval_log (source_type, source_id);
CREATE INDEX idx_retrieval_log_created      ON retrieval_log (created_at DESC);

-- RAG execution log
CREATE INDEX idx_exec_log_ticket        ON rag_execution_log (ticket_number);
CREATE INDEX idx_exec_log_conversation  ON rag_execution_log (conversation_id);
CREATE INDEX idx_exec_log_graph_type    ON rag_execution_log (graph_type);
CREATE INDEX idx_exec_log_created       ON rag_execution_log (created_at DESC);

-- Retrieval log -> execution log link
CREATE INDEX idx_retrieval_log_execution ON retrieval_log (execution_id);

-- Full-text search on source tables
CREATE INDEX idx_conversations_transcript_fts ON conversations
    USING gin (to_tsvector('english', coalesce(transcript, '')));
CREATE INDEX idx_tickets_description_fts ON tickets
    USING gin (to_tsvector('english', coalesce(description, '')));
CREATE INDEX idx_tickets_resolution_fts ON tickets
    USING gin (to_tsvector('english', coalesce(resolution, '')));

-- ═══════════════════════════════════════════════════════════════════════
-- SEED DATA
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO categories (name) VALUES
    ('General'),
    ('Advance Property Date'),
    ('HAP / Voucher Processing'),
    ('Certifications'),
    ('Move-Out'),
    ('Move-In'),
    ('TRACS File'),
    ('Close Bank Deposit'),
    ('Units / Move-In-Out'),
    ('Gross Rent Change'),
    ('Unit Transfer'),
    ('Waitlist'),
    ('Repayment Plan'),
    ('Security Deposit');

-- ═══════════════════════════════════════════════════════════════════════
-- RPC FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════

-- 1. Atomic confidence update with row-level locking
CREATE OR REPLACE FUNCTION update_corpus_confidence(
    p_source_type     TEXT,
    p_source_id       TEXT,
    p_delta           FLOAT,
    p_increment_usage BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    new_confidence  FLOAT,
    new_usage_count INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_confidence FLOAT;
    v_usage      INT;
BEGIN
    SELECT rc.confidence, rc.usage_count
      INTO v_confidence, v_usage
      FROM retrieval_corpus rc
     WHERE rc.source_type = p_source_type
       AND rc.source_id   = p_source_id
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'retrieval_corpus row not found: (%, %)', p_source_type, p_source_id;
    END IF;

    v_confidence := GREATEST(0.0, LEAST(1.0, v_confidence + p_delta));
    IF p_increment_usage THEN
        v_usage := v_usage + 1;
    END IF;

    UPDATE retrieval_corpus rc
       SET confidence  = v_confidence,
           usage_count = v_usage,
           updated_at  = now()
     WHERE rc.source_type = p_source_type
       AND rc.source_id   = p_source_id;

    new_confidence  := v_confidence;
    new_usage_count := v_usage;
    RETURN NEXT;
END;
$$;

-- 2. Vector similarity search against retrieval_corpus
CREATE OR REPLACE FUNCTION match_corpus(
    query_embedding        vector(3072),
    p_top_k                INTEGER DEFAULT 10,
    p_source_types         TEXT[]  DEFAULT NULL,
    p_category             TEXT    DEFAULT NULL,
    p_similarity_threshold FLOAT   DEFAULT 0.0
)
RETURNS TABLE (
    source_type TEXT,
    source_id   TEXT,
    title       TEXT,
    content     TEXT,
    category    TEXT,
    module      TEXT,
    tags        TEXT,
    similarity  FLOAT,
    confidence  FLOAT,
    usage_count INTEGER,
    updated_at  TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.source_type,
        rc.source_id,
        rc.title,
        rc.content,
        rc.category,
        rc.module,
        rc.tags,
        (1 - (rc.embedding <=> query_embedding))::FLOAT AS similarity,
        rc.confidence,
        rc.usage_count,
        rc.updated_at
    FROM retrieval_corpus rc
    WHERE
        (p_source_types IS NULL OR rc.source_type = ANY(p_source_types))
        AND (p_category IS NULL OR rc.category ILIKE '%' || p_category || '%')
        AND (1 - (rc.embedding <=> query_embedding)) >= p_similarity_threshold
    ORDER BY rc.embedding <=> query_embedding ASC
    LIMIT p_top_k;
END;
$$;

-- 3. Increment usage count after successful retrieval
CREATE OR REPLACE FUNCTION increment_corpus_usage(
    p_source_type TEXT,
    p_source_id   TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE retrieval_corpus
    SET usage_count = usage_count + 1,
        updated_at  = now()
    WHERE source_type = p_source_type
      AND source_id   = p_source_id;
END;
$$;
