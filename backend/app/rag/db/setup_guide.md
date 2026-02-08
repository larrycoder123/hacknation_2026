# SupportMind RAG — Supabase Setup Guide

## Prerequisites

- Supabase project with pgvector extension enabled
- `retrieval_corpus` table already created (see `backend/supabase/` migrations)

## Step 1: Deploy RPC Functions

Run `rpc_functions.sql` in the Supabase SQL Editor. This creates:

1. **`retrieval_log`** table — tracks every RAG retrieval attempt
2. **`match_corpus()`** RPC — vector similarity search against `retrieval_corpus`
3. **`increment_corpus_usage()`** — bumps usage stats after successful retrieval

## Step 2: Verify

```sql
-- Check match_corpus exists
SELECT proname FROM pg_proc WHERE proname = 'match_corpus';

-- Check retrieval_log table
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'retrieval_log';
```

## Key Tables

| Table | Purpose |
|-------|---------|
| `retrieval_corpus` | Unified vector space (scripts, KB articles, ticket resolutions) |
| `retrieval_log` | Audit trail of every RAG search |
| `kb_lineage` | Provenance: KB article → ticket/conversation/script |
| `scripts_master` | Canonical Tier 3 fix scripts |
| `tickets` / `conversations` | Source cases and transcripts |

## Environment Variables

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=your-openai-key
COHERE_API_KEY=your-cohere-key  # Optional, for reranking
```
