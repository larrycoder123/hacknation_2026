-- 005: RAG execution log table + execution_id on retrieval_log
-- One row per gap detection pipeline run. Captures latency, tokens, classification.

CREATE TABLE IF NOT EXISTS rag_execution_log (
    execution_id     TEXT PRIMARY KEY,
    graph_type       TEXT NOT NULL CHECK (graph_type IN ('QA', 'GAP_DETECTION')),
    conversation_id  TEXT,
    ticket_number    TEXT,
    query            TEXT,
    total_latency_ms INT,
    node_latencies   JSONB,
    tokens_input     INT DEFAULT 0,
    tokens_output    INT DEFAULT 0,
    evidence_count   INT DEFAULT 0,
    top_similarity   FLOAT,
    top_rerank_score FLOAT,
    classification   TEXT,
    status           TEXT DEFAULT 'success',
    error_message    TEXT,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exec_log_ticket       ON rag_execution_log (ticket_number);
CREATE INDEX IF NOT EXISTS idx_exec_log_conversation ON rag_execution_log (conversation_id);
CREATE INDEX IF NOT EXISTS idx_exec_log_graph_type   ON rag_execution_log (graph_type);
CREATE INDEX IF NOT EXISTS idx_exec_log_created      ON rag_execution_log (created_at DESC);

-- Link retrieval_log rows to their pipeline run
DO $$ BEGIN
    ALTER TABLE retrieval_log ADD COLUMN execution_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_retrieval_log_execution ON retrieval_log (execution_id);
