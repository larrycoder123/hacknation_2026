# SupportMind RAG Component

The retrieval-augmented generation engine for SupportMind. This component is the core intelligence layer that powers two critical capabilities: answering support questions in real time, and detecting knowledge gaps to feed the self-learning loop.

## Why This Exists

Support knowledge at scale is fragmented across three silos:

1. **Scripts** (999 entries) — Backend SQL data-fix scripts used by Tier 3 support to resolve complex issues. Each has sanitized placeholders (`<DATABASE>`, `<SITE_NAME>`, etc.) and requires specific inputs.
2. **KB Articles** (3,207 entries) — A mix of 3,046 seed articles and 161 synthetic articles auto-generated from resolved tickets.
3. **Ticket Resolutions** (400 populated) — Closed cases with descriptions, resolutions, and root causes that contain institutional knowledge never formalized into KB articles.

All three are embedded into a single **`retrieval_corpus`** table using `text-embedding-3-large` (3072 dimensions) so a single vector search can surface the best resource regardless of type. This RAG component searches that corpus, enriches results with metadata from connected tables, and either answers questions or classifies whether a ticket represents new knowledge.

## What It Does

### 1. Question Answering (QA Graph)

Takes a support question, finds the most relevant scripts/KB articles/ticket resolutions, enriches them with provenance and metadata, and generates a cited answer.

**When it runs:** A support agent or customer asks a question through the UI.

```python
from app.rag import run_rag

result = run_rag(
    question="How do I advance the property date when the backend sync is failing?",
    category="Advance Property Date",      # optional, narrows vector search
    source_types=["SCRIPT", "KB"],         # optional, filter by type
    top_k=10,                              # evidence items to use
    ticket_number="CS-38908386",           # optional, links retrieval logs
)

print(result.answer)          # Generated answer with inline citations
print(result.citations)       # List of Citation(source_type, source_id, title, quote)
print(result.top_hits)        # Raw CorpusHit objects for caller inspection
print(result.status)          # "success" | "insufficient_evidence" | "error"
print(result.to_context())    # Formatted string for passing to another LLM
```

**QA Graph flow:**

```
plan_query ──> retrieve ──> rerank ──> enrich_sources ──> write_answer ──> validate ──> log_retrieval ──> END
                  ^                                                            |
                  └──── retry (expand top_k by 1.5x, max 1 retry) ────────────┘
```

### 2. Gap Detection (Learning Loop Graph)

Takes a resolved ticket and determines whether its knowledge already exists in the corpus, contradicts existing knowledge, or represents something entirely new. This is the trigger for the self-learning loop — when `NEW_KNOWLEDGE` is detected, a KB article draft should be generated.

**When it runs:** After a Tier 3 ticket is closed, the learning loop component calls this to check if the corpus already covers the resolution.

```python
from app.rag import run_gap_detection
from app.rag.models.corpus import GapDetectionInput

result = run_gap_detection(GapDetectionInput(
    ticket_number="CS-38908386",
    conversation_id="CONV-O2RAK1VRJN",
    category="Advance Property Date",
    subject="Unable to advance property date (backend data sync)",
    description="Customer reports property date cannot be advanced...",
    resolution="Applied backend data-fix script SCRIPT-0293. Customer confirmed.",
    root_cause="Data inconsistency requiring backend fix",
    script_id="SCRIPT-0293",
))

print(result.decision.decision)    # "SAME_KNOWLEDGE" | "CONTRADICTS" | "NEW_KNOWLEDGE"
print(result.decision.reasoning)   # LLM explanation of why
print(result.decision.similarity_score)  # Best match similarity (0-1)
print(result.decision.best_match_source_id)  # Closest corpus entry ID
print(result.retrieved_entries)    # What the search found
print(result.enriched_sources)     # Metadata from connected tables
```

**Gap Detection Graph flow:**

```
plan_query ──> retrieve ──> rerank ──> enrich_sources ──> classify_knowledge ──> log_retrieval ──> END
```

**Classification logic:**
- `SAME_KNOWLEDGE` — Resolution matches existing corpus entries (similarity > 0.75, same resolution steps)
- `CONTRADICTS` — Same topic but different/conflicting resolution (suggests existing KB may be outdated)
- `NEW_KNOWLEDGE` — No adequate coverage exists (triggers KB article drafting)

## How It Works: Node-by-Node

Both graphs share the same retrieval pipeline (nodes 1-4), then diverge:

### Shared Nodes

| Node | What It Does | LLM Call? | DB Call? |
|------|-------------|-----------|----------|
| **`plan_query`** | GPT-4o generates 2-4 search query variants from the input question. Understands SupportMind categories, module names, and resolution patterns. | Yes (structured output) | No |
| **`retrieve`** | Embeds each query variant with `text-embedding-3-large`, calls `match_corpus()` RPC for each, deduplicates results by composite key `(source_type, source_id)`, keeps the highest similarity per entry. Returns up to 40 candidates. | No | Yes (1 RPC per query variant) |
| **`rerank`** | Cohere reranks all candidates by relevance. Falls back to similarity order if no Cohere API key. Returns top_k evidence items. | No | No |
| **`enrich_sources`** | Batch-lookups from connected tables (max 3 DB calls). KB hits get lineage (linked ticket/conversation/script from `kb_lineage`). Script hits get purpose and required inputs from `scripts_master`. Ticket hits get subject/resolution/root_cause from `tickets`. | No | Yes (up to 3 batch queries) |

### QA-Only Nodes

| Node | What It Does | LLM Call? |
|------|-------------|-----------|
| **`write_answer`** | GPT-4o generates a cited answer using the evidence + enrichment data. Returns structured `RagAnswer` with answer text, citations, and confidence. | Yes (structured output) |
| **`validate`** | Checks that the answer has at least 1 evidence item and at least 1 citation. If validation fails and attempt < 1, retries with top_k expanded by 1.5x. After 1 retry, returns `INSUFFICIENT_EVIDENCE`. | No |

### Gap Detection-Only Nodes

| Node | What It Does | LLM Call? |
|------|-------------|-----------|
| **`classify_knowledge`** | If no evidence found, immediately returns `NEW_KNOWLEDGE`. Otherwise, GPT-4o (temperature=0) classifies the ticket's knowledge against the top 5 matches considering similarity scores, resolution steps, and root cause alignment. | Yes (structured output, temp=0) |

### Both Graphs End With

| Node | What It Does | DB Call? |
|------|-------------|----------|
| **`log_retrieval`** | Writes a `RetrievalLogEntry` row per evidence item (up to 10) to the `retrieval_log` table. Also calls `increment_corpus_usage()` for the top 5 hits to track which entries are most useful. Failures are logged but don't break the pipeline. | Yes |

## Data Flow Diagram

```
                    ┌──────────────────────────────────┐
                    │         retrieval_corpus           │
                    │  (SCRIPT, KB, TICKET_RESOLUTION)   │
                    │  3072-dim embeddings (pgvector)     │
                    └──────────┬───────────────────────┘
                               │
                          match_corpus() RPC
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                          │                           │
    │  ┌───────────────────────▼────────────────────────┐  │
    │  │              RAG Pipeline                       │  │
    │  │                                                 │  │
    │  │  plan_query ─> retrieve ─> rerank ─> enrich     │  │
    │  │                                │                │  │
    │  │           ┌────────────────────┤                │  │
    │  │           │                    │                │  │
    │  │    QA branch:           Gap branch:             │  │
    │  │    write_answer         classify_knowledge      │  │
    │  │    validate             (SAME/CONTRA/NEW)       │  │
    │  │           │                    │                │  │
    │  │           └────────┬───────────┘                │  │
    │  │                    │                             │  │
    │  │              log_retrieval                       │  │
    │  └────────────────────┼────────────────────────────┘  │
    │                       │                               │
    │                       ▼                               │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │  Enrichment Sources (batch lookups)              │  │
    │  │  ┌─────────────┐ ┌──────────────┐ ┌──────────┐  │  │
    │  │  │ kb_lineage   │ │scripts_master│ │ tickets  │  │  │
    │  │  │ (provenance) │ │ (purpose,    │ │(subject, │  │  │
    │  │  │              │ │  inputs)     │ │ root     │  │  │
    │  │  │              │ │              │ │ cause)   │  │  │
    │  │  └─────────────┘ └──────────────┘ └──────────┘  │  │
    │  └─────────────────────────────────────────────────┘  │
    │                       │                               │
    │                       ▼                               │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │              retrieval_log                       │  │
    │  │  (audit trail of every search attempt)           │  │
    │  └─────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────┘
```

## Key Models

### Input/Output Contracts

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `RagInput` | QA input | `question`, `category`, `source_types`, `top_k`, `ticket_number` |
| `RagResult` | QA output | `answer`, `citations`, `status`, `top_hits`, `to_context()` |
| `GapDetectionInput` | Gap detection input | `ticket_number`, `subject`, `resolution`, `root_cause`, `category`, `script_id` |
| `GapDetectionResult` | Gap detection output | `decision` (KnowledgeDecision), `retrieved_entries`, `enriched_sources`, `query_used` |

### Internal State

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `CorpusHit` | A retrieved entry from `retrieval_corpus` | `source_type`, `source_id`, `content`, `similarity`, `rerank_score`, `confidence`, `usage_count` |
| `SourceDetail` | Enriched metadata from connected tables | KB: `lineage_ticket/conversation/script`. Script: `script_purpose`, `script_inputs`. Ticket: `ticket_subject/resolution/root_cause` |
| `Citation` | A source reference in the answer | `source_type`, `source_id`, `title`, `quote` |
| `KnowledgeDecision` | Gap classification result | `decision` (SAME/CONTRADICTS/NEW), `reasoning`, `best_match_source_id`, `similarity_score` |
| `RetrievalLogEntry` | Audit log row | `retrieval_id`, `ticket_number`, `query_text`, `source_type`, `source_id`, `similarity_score`, `outcome` |

## Database Dependencies

### Tables Read

| Table | What We Read | When |
|-------|-------------|------|
| `retrieval_corpus` | Vector search via `match_corpus()` RPC | Every query (retrieve node) |
| `kb_lineage` | Provenance links for KB articles | enrich_sources, when KB hits found |
| `scripts_master` | Script purpose and required inputs | enrich_sources, when SCRIPT hits found |
| `tickets` | Subject, resolution, root cause | enrich_sources, when TICKET_RESOLUTION hits found |

### Tables Written

| Table | What We Write | When |
|-------|-------------|------|
| `retrieval_log` | One row per evidence item per query | log_retrieval node (end of both graphs) |
| `retrieval_corpus` | Increment `usage_count` + `updated_at` | log_retrieval node (top 5 hits) |

### RPC Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `match_corpus()` | `(query_embedding vector(3072), p_top_k, p_source_types[], p_category, p_similarity_threshold)` | Vector similarity search with optional filtering |
| `increment_corpus_usage()` | `(p_source_type, p_source_id)` | Bump usage count after successful retrieval |

Deploy these by running `db/rpc_functions.sql` in the Supabase SQL Editor.

## Configuration

All settings are in `core/config.py`, loaded from environment variables:

| Setting | Default | Purpose |
|---------|---------|---------|
| `openai_api_key` | `""` | OpenAI API key |
| `openai_embedding_model` | `text-embedding-3-large` | Embedding model |
| `openai_chat_model` | `gpt-4o` | Chat/structured output model |
| `embedding_dimension` | `3072` | Vector dimension (must match DB column) |
| `cohere_api_key` | `""` | Cohere API key (optional, for reranking) |
| `cohere_rerank_model` | `rerank-english-v3.0` | Rerank model |
| `supabase_url` | `""` | Supabase project URL |
| `supabase_service_role_key` | `""` | Supabase service role key |
| `default_top_k` | `10` | Default evidence items to return |
| `max_retrieval_candidates` | `40` | Max candidates before reranking |
| `gap_similarity_threshold` | `0.75` | Similarity threshold for gap detection |

## Folder Structure

```
app/rag/
├── __init__.py                # Public API: run_rag(), run_gap_detection()
├── REWRITE_SUMMARY.md         # What changed from the old PDF-based RAG
│
├── core/                      # Shared infrastructure (no business logic)
│   ├── config.py              # Settings via pydantic-settings
│   ├── embedder.py            # OpenAI text-embedding-3-large (3072d)
│   ├── llm.py                 # OpenAI gpt-4o + TokenUsage tracking
│   ├── reranker.py            # Cohere reranking (fallback to similarity order)
│   └── supabase_client.py     # LRU-cached Supabase client factory
│
├── models/                    # Pydantic v2 contracts (all boundaries typed)
│   ├── rag.py                 # CorpusHit, RagInput, RagResult, RagState, Citation
│   ├── corpus.py              # GapDetectionInput, KnowledgeDecision, GapDetectionResult
│   └── retrieval_log.py       # RetrievalLogEntry, RetrievalOutcome
│
├── agent/                     # LangGraph workflows
│   ├── prompts.py             # 3 versioned prompt templates
│   ├── nodes.py               # 7 node functions (plan, retrieve, rerank, enrich, answer, classify, log)
│   └── graph.py               # QA graph + gap detection graph + entry points
│
├── db/                        # Database setup
│   ├── rpc_functions.sql      # match_corpus() RPC + retrieval_log table + increment_corpus_usage()
│   └── setup_guide.md         # Supabase setup instructions
│
└── tests/                     # 37 tests, all passing
    ├── test_rag.py            # Model validation (25 tests)
    └── test_nodes.py          # Node logic with mocked deps (12 tests)
```

## How This Connects to the Self-Learning Loop

This RAG component is step 1 in the broader SupportMind learning pipeline:

```
1. Ticket resolved
       │
       ▼
2. Gap Detection (this component)
   run_gap_detection() → SAME / CONTRADICTS / NEW_KNOWLEDGE
       │
       ├── SAME_KNOWLEDGE → No action needed
       ├── CONTRADICTS → Flag for review (existing KB may be outdated)
       └── NEW_KNOWLEDGE → Triggers step 3
       │
       ▼
3. Draft KB Article (draft_generator service)
   LLM extracts structured KB from ticket + conversation + script
       │
       ▼
4. Human Review (review service)
   Tier 3 Support or Support Ops approves/rejects
       │
       ▼
5. Publish (publisher service)
   Approved article → Knowledge_Articles + KB_Lineage + re-embed into retrieval_corpus
       │
       ▼
6. Verification
   run_rag() with a question from Questions tab → new article now retrievable
```

## Running Tests

```bash
cd backend
python -m pytest app/rag/tests/ -v          # all 37 tests
python -m pytest app/rag/tests/test_rag.py  # model tests only
python -m pytest app/rag/tests/test_nodes.py # node tests only (mocked)
```

## Setup

```bash
# 1. Install dependencies
pip install -r app/rag/requirements.txt

# 2. Set environment variables
export OPENAI_API_KEY=sk-...
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=eyJ...
export COHERE_API_KEY=...  # optional

# 3. Deploy RPC functions to Supabase
# Paste db/rpc_functions.sql into Supabase SQL Editor and run

# 4. Verify
python -c "from app.rag import run_rag, run_gap_detection; print('OK')"
```
