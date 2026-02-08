# RAG Rewrite Summary

## What Changed

The RAG component was rewritten from a generic PDF ingestion + chunk retrieval system
to a SupportMind-specific knowledge retrieval and gap detection system.

### Removed
- **Ingestion pipeline** (`ingestion/` directory) — PDF parsing, chunking, deduplication
- **Chunk-based models** — `ChunkHit`, `IngestInput`, `Page`, `Chunk`, `IngestionResult`
- **Old DB schema** (`db/schema.sql`) — `documents`, `chunks`, `ingestion_runs` tables
- **`agentic_backend.logging`** dependency — broken import replaced with inline `TokenUsage`
- **Dependencies** — `pypdf`, `tiktoken` removed

### Added
- **Gap detection graph** — classifies resolved tickets as SAME/CONTRADICTS/NEW knowledge
- **Corpus-based models** — `CorpusHit`, `SourceDetail`, `GapDetectionInput`, `GapDetectionResult`
- **Source enrichment node** — batch-lookups from `kb_lineage`, `scripts_master`, `tickets`
- **Retrieval logging** — `retrieval_log` table tracks every RAG attempt
- **Versioned prompts** (`agent/prompts.py`) — domain-aware templates for SupportMind
- **`match_corpus()` RPC** — vector search against `retrieval_corpus` with source type filtering

### Upgraded
- **Embedding model**: `text-embedding-3-small` (1536d) → `text-embedding-3-large` (3072d)
- **Chat model**: `gpt-4o-mini` → `gpt-4o`
- **DB target**: `chunks` table → `retrieval_corpus` table

## Why

The previous RAG was built for a different project (generic document Q&A). SupportMind
needs retrieval against a unified `retrieval_corpus` containing scripts, KB articles,
and ticket resolutions — with enrichment from connected tables and a gap detection
pipeline for the self-learning loop.
