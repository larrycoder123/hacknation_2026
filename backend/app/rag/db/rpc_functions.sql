-- =============================================================================
-- SupportMind RAG: retrieval_log table + match_corpus() RPC
-- Run this in Supabase SQL Editor
-- =============================================================================

-- 1. Retrieval log table
-- One row per retrieval attempt, tied to a ticket for tracking effectiveness.
CREATE TABLE IF NOT EXISTS retrieval_log (
    retrieval_id     TEXT PRIMARY KEY,
    ticket_number    TEXT,
    attempt_number   INT NOT NULL DEFAULT 1,
    query_text       TEXT,
    source_type      TEXT,
    source_id        TEXT,
    similarity_score FLOAT,
    outcome          TEXT CHECK (outcome IN ('RESOLVED', 'UNHELPFUL', 'PARTIAL')),
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_log_ticket
    ON retrieval_log(ticket_number);

CREATE INDEX IF NOT EXISTS idx_retrieval_log_created
    ON retrieval_log(created_at DESC);


-- 2. match_corpus() RPC function
-- Vector similarity search against the retrieval_corpus table.
-- Supports optional filtering by source_types and category.
CREATE OR REPLACE FUNCTION match_corpus(
    query_embedding  vector(3072),
    p_top_k          INTEGER DEFAULT 10,
    p_source_types   TEXT[]  DEFAULT NULL,
    p_category       TEXT    DEFAULT NULL,
    p_similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    source_type      TEXT,
    source_id        TEXT,
    title            TEXT,
    content          TEXT,
    category         TEXT,
    module           TEXT,
    tags             TEXT,
    similarity       FLOAT,
    confidence       FLOAT,
    usage_count      INTEGER,
    updated_at       TIMESTAMPTZ
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


-- 3. increment_corpus_usage() helper
-- Bumps usage_count and updated_at for a corpus entry after successful retrieval.
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
