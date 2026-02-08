# SupportMind — Self-Learning Support Intelligence

Hackathon project (hacknation 2026) sponsored by RealPage. SupportMind is a self-learning AI layer for customer support: it recommends scripts/KB articles during live conversations, then learns from resolved tickets to grow the knowledge base automatically.

## How It Works (End to End)

```
┌──────────────────────────────────────────────────────────┐
│  1. Agent opens a conversation                           │
│     Frontend loads messages from backend mock data       │
│                                                          │
│  2. Agent clicks "Analyze" (suggested actions)           │
│     Frontend: GET /api/conversations/{id}/suggested-actions
│     Backend runs RAG pipeline → returns top matches      │
│     from scripts, KB articles, and past ticket fixes     │
│                                                          │
│  3. Agent resolves the issue using suggestions           │
│                                                          │
│  4. Agent closes conversation                            │
│     Frontend: POST /api/conversations/{id}/close         │
│     Backend:                                             │
│       a) LLM generates a structured ticket               │
│       b) Ticket saved to Supabase                        │
│       c) Self-learning pipeline runs:                    │
│          - Score past RAG lookups (confidence updates)   │
│          - Fresh gap detection search                    │
│          - Classify: SAME / CONTRADICTS / NEW knowledge  │
│          - Draft new KB article if gap found             │
│       d) Returns ticket + learning result to frontend    │
│                                                          │
│  5. Reviewer approves/rejects KB draft                   │
│     Frontend: POST /api/learning-events/{id}/review      │
│     Approved → KB article activated, added to corpus     │
│     Rejected → Draft archived                            │
└──────────────────────────────────────────────────────────┘
```

## Architecture

```
Frontend (Next.js 16)           Backend (FastAPI)              External Services
─────────────────────           ─────────────────              ─────────────────
page.tsx                        /api/conversations/*           Supabase (Postgres + pgvector)
  ConversationQueue             /api/tickets/{id}/learn        OpenAI API (GPT, embeddings)
  ConversationDetail            /api/learning-events/{id}/rev  Cohere API (reranking)
  AIAssistant (suggestions)
  CloseConversationModal        Services:
                                  ticket_service (LLM ticket gen)
api/client.ts ──HTTP──────────►   learning_service (self-learning)
                                  RAG pipeline (LangGraph)
```

### Two Supabase Clients

The backend has **two separate Supabase client singletons** — be aware of this:

| Client | Location | Uses Key | Used By |
|--------|----------|----------|---------|
| App client | `app/db/client.py` | `SUPABASE_KEY` | ticket_service, learning_service |
| RAG client | `app/rag/core/supabase_client.py` | `SUPABASE_SERVICE_ROLE_KEY` | RAG nodes (retrieve, enrich, log) |

Both are thread-safe singletons. The RAG client uses the service role key because it needs to call RPC functions directly.

### Two Settings Classes

| Settings | Location | Env Vars |
|----------|----------|----------|
| App settings | `app/core/config.py` | `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`, confidence deltas |
| RAG settings | `app/rag/core/config.py` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, `COHERE_API_KEY` |

Both read from the same `.env` file at the project root.

---

## Database (Supabase)

### Tables

```
┌─────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│   conversations     │────►│      tickets         │────►│   scripts_master   │
│                     │     │                      │     │                    │
│ ticket_number (PK)  │     │ ticket_number (PK)   │     │ script_id (PK)     │
│ conversation_id     │     │ conversation_id (FK)  │     │ script_title       │
│ channel             │     │ subject              │     │ script_purpose     │
│ transcript          │     │ description          │     │ category           │
│ category            │     │ resolution           │     │ module             │
│ issue_summary       │     │ root_cause           │     │ script_text_sanitized│
│ sentiment           │     │ category             │     └────────────────────┘
└─────────────────────┘     │ tags                 │
                            │ script_id (FK)───────┘
                            │ priority             │
                            │ kb_article_id (FK)───────────────────┐
                            │ generated_kb_article_id (FK)─────┐   │
                            └──────────────────────┘           │   │
                                                               ▼   ▼
┌─────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  retrieval_corpus   │     │   learning_events    │     │ knowledge_articles │
│  (vector search)    │     │                      │     │                    │
│                     │     │ event_id (PK)        │     │ kb_article_id (PK) │
│ source_type (PK)    │     │ trigger_ticket_number│     │ title              │
│ source_id   (PK)    │     │ detected_gap         │     │ body               │
│ title               │     │ event_type           │     │ tags, module       │
│ content             │     │   GAP / CONTRADICTION│     │ category           │
│ category            │     │   / CONFIRMED        │     │ source_type        │
│ module              │     │ proposed_kb_article_id│     │   SEED_KB          │
│ tags                │     │ flagged_kb_article_id │     │   SYNTH_FROM_TICKET│
│ embedding (3072d)   │     │ draft_summary        │     │ status (Active)    │
│ confidence (0-1)    │     │ final_status         │     └────────────────────┘
│ usage_count         │     │   Approved / Rejected│
│ updated_at          │     │ reviewer_role        │
└─────────────────────┘     └──────────────────────┘

┌─────────────────────┐     ┌──────────────────────┐
│   retrieval_log     │     │     kb_lineage       │
│                     │     │                      │
│ retrieval_id (PK)   │     │ kb_article_id (FK)   │
│ ticket_number       │     │ source_type          │
│ conversation_id     │     │   Ticket/Conv/Script │
│ attempt_number      │     │ source_id            │
│ query_text          │     │ relationship         │
│ source_type         │     │   CREATED_FROM       │
│ source_id           │     │   REFERENCES         │
│ similarity_score    │     │ evidence_snippet     │
│ outcome             │     └──────────────────────┘
│   RESOLVED/PARTIAL  │
│   /UNHELPFUL        │
│ created_at          │
└─────────────────────┘
```

### `retrieval_corpus` — The Unified Vector Space

This is the main table the RAG searches. It holds **three types of knowledge**, all embedded in the same 3072-dimensional vector space:

| source_type | source_id points to | What it contains |
|-------------|---------------------|------------------|
| `SCRIPT` | `scripts_master.script_id` | Script purpose + sanitized SQL |
| `KB` | `knowledge_articles.kb_article_id` | KB article title + body |
| `TICKET_RESOLUTION` | `tickets.ticket_number` | Ticket subject + resolution + root cause |

Composite primary key: `(source_type, source_id)`.

`confidence` starts at 1.0 and gets adjusted by the learning pipeline (+0.10 for RESOLVED outcomes, -0.05 for UNHELPFUL). `usage_count` tracks how often each entry was retrieved.

### `retrieval_log` — RAG Audit Trail

Every RAG search writes rows here. The lifecycle:

1. **During live support** (suggested actions): RAG writes logs with `conversation_id` only (no ticket exists yet)
2. **On conversation close**: Backend stamps `ticket_number` onto all logs for that `conversation_id`
3. **Learning pipeline**: Reads logs by `ticket_number`, bulk-sets outcomes (RESOLVED/UNHELPFUL), updates confidence

### `learning_events` — Self-Learning Audit

One row per learning pipeline run. Three event types:

| event_type | Meaning | What happens |
|------------|---------|--------------|
| `CONFIRMED` | Existing KB already covers this knowledge | Confidence boosted on matched KB |
| `GAP` | No matching KB found above similarity threshold | New KB article drafted |
| `CONTRADICTION` | Existing KB found but content conflicts | Replacement KB drafted, old one flagged |

GAP and CONTRADICTION events create a draft KB article (`proposed_kb_article_id`) that needs human review. CONFIRMED events are auto-approved.

### `kb_lineage` — Provenance Chain

Every synthetic KB article (`KB-SYN-*`) has 3 lineage records tracing back to its sources:
- `CREATED_FROM` Ticket
- `CREATED_FROM` Conversation
- `REFERENCES` Script

### Required RPC Functions

These must exist in Supabase (run via SQL Editor):

| Function | Purpose | Definition |
|----------|---------|------------|
| `match_corpus(query_embedding, p_top_k, p_source_types, p_category)` | Vector similarity search on `retrieval_corpus` | `backend/app/rag/db/rpc_functions.sql` |
| `increment_corpus_usage(p_source_type, p_source_id)` | Bump usage_count after successful retrieval | Same file |
| `update_corpus_confidence(p_source_type, p_source_id, p_delta, p_increment_usage)` | Adjust confidence score | `backend/HANDOFF_DATABASE.md` |

---

## RAG Pipeline

Built with **LangGraph** — two separate graphs sharing the same node functions.

### QA Graph (suggested actions)

Called when the agent clicks "Analyze" on a conversation.

```
plan_query ──► retrieve ──► rerank ──► enrich_sources ──► write_answer ──► validate ──► log_retrieval
                  ▲                                                           │
                  └───────────────── retry (wider search) ◄───────────────────┘
```

| Node | What it does |
|------|-------------|
| `plan_query` | LLM generates 2-4 search query variants from the question |
| `retrieve` | Embeds each variant (text-embedding-3-large, 3072d), calls `match_corpus` RPC, deduplicates by `(source_type, source_id)`, keeps top 40 |
| `rerank` | Cohere reranker (rerank-v4.0-pro) narrows to top_k |
| `enrich_sources` | Batch lookups: KB → `kb_lineage`, SCRIPT → `scripts_master`, TICKET → `tickets` |
| `write_answer` | LLM generates answer with citations referencing sources |
| `validate` | Checks evidence count + citations. If insufficient and attempt < 1, retries with wider top_k |
| `log_retrieval` | Writes `retrieval_log` rows + increments `usage_count` on corpus entries |

Entry point: `run_rag(question, category?, source_types?, top_k?, ticket_number?, conversation_id?)`

### Gap Detection Graph (learning loop)

Called when a conversation closes, as part of the self-learning pipeline.

```
plan_query ──► retrieve ──► rerank ──► enrich_sources ──► classify_knowledge ──► log_retrieval
```

| Node | What it does |
|------|-------------|
| `classify_knowledge` | LLM classifies as SAME_KNOWLEDGE / CONTRADICTS / NEW_KNOWLEDGE based on similarity scores + content comparison |

Entry point: `run_gap_detection(GapDetectionInput)` — query is built from the ticket's subject, root cause, category, and resolution.

---

## Self-Learning Pipeline

Defined in `backend/app/services/learning_service.py`. Runs synchronously during conversation close.

```
Stage 0: Link retrieval logs
         UPDATE retrieval_log SET ticket_number = $1
         WHERE conversation_id = $2 AND ticket_number IS NULL

Stage 1: Score past RAG lookups
         Fetch retrieval_log rows for this ticket
         Bulk-set outcomes: RESOLVED (if conversation resolved) or UNHELPFUL
         Update confidence on each corpus entry:
           RESOLVED  → +0.10
           PARTIAL   → +0.02
           UNHELPFUL → -0.05

Stage 2: Fresh gap detection
         Fetch ticket + conversation from DB
         Build query from: subject + root_cause + category + resolution
         Run gap detection graph (embed → search → rerank → classify)

Stage 3: Act on classification
         SAME_KNOWLEDGE  → log CONFIRMED event, boost matched KB confidence
         NEW_KNOWLEDGE   → draft new KB article via LLM, create GAP event
         CONTRADICTS     → draft replacement, flag old KB, create CONTRADICTION event
```

### KB Draft → Review → Publish

GAP and CONTRADICTION events produce a draft KB article in `knowledge_articles` (status = "Draft") and a `learning_events` row with `final_status = NULL`.

The review endpoint (`POST /api/learning-events/{id}/review`) handles approval:

| Decision | GAP event | CONTRADICTION event |
|----------|-----------|---------------------|
| **Approved** | Set KB status → Active, embed into `retrieval_corpus` | Replace old KB content with draft, re-embed, archive draft |
| **Rejected** | Set KB status → Archived, remove from `retrieval_corpus` | Keep existing KB, archive draft |

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/conversations` | List all conversations |
| GET | `/api/conversations/{id}` | Get single conversation |
| GET | `/api/conversations/{id}/messages` | Get message history |
| GET | `/api/conversations/{id}/suggested-actions` | RAG-powered suggestions (scripts/KB/tickets) |
| POST | `/api/conversations/{id}/close` | Close conversation → generate ticket → run learning |
| POST | `/api/tickets/{id}/learn` | Manual learning trigger (for testing) |
| POST | `/api/learning-events/{id}/review` | Approve/reject KB draft |
| GET | `/` | Health check |

### Close Conversation Response

```json
{
  "status": "success",
  "message": "Conversation conv-123 closed successfully",
  "ticket": {
    "ticket_number": "CS-A1B2C3D4",
    "subject": "Unable to advance property date",
    "description": "...",
    "resolution": "Applied backend data-fix script...",
    "tags": ["date-advance", "backend-fix"]
  },
  "warnings": [],
  "learning_result": {
    "ticket_number": "CS-A1B2C3D4",
    "retrieval_logs_processed": 3,
    "confidence_updates": [{"source_type": "SCRIPT", "source_id": "SCRIPT-0293", "delta": 0.1, "new_confidence": 1.0, "new_usage_count": 4}],
    "gap_classification": "NEW_KNOWLEDGE",
    "learning_event_id": "LE-abc123def456",
    "drafted_kb_article_id": "KB-SYN-A1B2C3D4"
  }
}
```

The frontend shows the ticket number and learning classification as system messages in the chat.

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                        # FastAPI app, CORS, router registration
│   ├── core/
│   │   ├── config.py                  # App settings (env vars)
│   │   └── llm.py                     # LangChain ChatOpenAI wrapper
│   ├── api/
│   │   ├── conversation_routes.py     # Conversation + close + suggested-actions
│   │   └── learning_routes.py         # /tickets/{id}/learn + /learning-events/{id}/review
│   ├── schemas/
│   │   ├── actions.py                 # SuggestedAction
│   │   ├── conversations.py           # Conversation, ClosePayload, CloseResponse
│   │   ├── messages.py                # Message
│   │   ├── tickets.py                 # Ticket, TicketDBRow, Priority
│   │   └── learning.py               # SelfLearningResult, KBDraft, LearningEvent, ReviewDecision
│   ├── services/
│   │   ├── ticket_service.py          # LLM ticket generation + DB persistence
│   │   └── learning_service.py        # Self-learning pipeline (confidence + gap detection + KB drafting)
│   ├── db/
│   │   └── client.py                  # Thread-safe Supabase singleton
│   ├── data/
│   │   ├── conversations.py           # Mock conversation/message data
│   │   └── suggestions.py             # Mock suggested actions (fallback)
│   └── rag/                           # RAG subsystem (self-contained)
│       ├── core/
│       │   ├── config.py              # RAG settings (models, thresholds)
│       │   ├── llm.py                 # OpenAI chat with structured output
│       │   ├── embedder.py            # text-embedding-3-large (3072d)
│       │   ├── reranker.py            # Cohere rerank-v4.0-pro
│       │   └── supabase_client.py     # RAG's own Supabase client
│       ├── agent/
│       │   ├── graph.py               # LangGraph: QA graph + gap detection graph
│       │   ├── nodes.py               # Node functions (plan, retrieve, rerank, enrich, write, classify, log)
│       │   └── prompts.py             # System prompts for LLM nodes
│       ├── models/
│       │   ├── rag.py                 # RagInput, RagState, RagResult, CorpusHit, Citation
│       │   ├── corpus.py              # GapDetectionInput, GapDetectionResult, KnowledgeDecision
│       │   └── retrieval_log.py       # RetrievalLogEntry, RetrievalOutcome
│       ├── db/
│       │   └── rpc_functions.sql      # match_corpus() + increment_corpus_usage() SQL
│       └── tests/
│           ├── test_rag.py            # Model tests
│           └── test_nodes.py          # Node function tests
├── scripts/
│   └── seed_mock_data.py             # Seed/cleanup mock data for testing
├── HANDOFF_FRONTEND.md               # Frontend changes needed (types, close flow)
├── HANDOFF_DATABASE.md               # DB migrations needed (learning_events, retrieval_log)
└── .env.example

frontend/
├── app/
│   ├── page.tsx                       # Main UI (conversation queue + detail + AI assistant)
│   ├── layout.tsx                     # Root layout
│   ├── types.ts                       # TypeScript types matching backend schemas
│   └── api/
│       └── client.ts                  # API client (fetch wrappers)
└── components/
    ├── ConversationQueue.tsx          # Left sidebar: conversation list
    ├── ConversationDetail.tsx         # Center: message history + input
    ├── AIAssistant.tsx                # Right sidebar: RAG suggestions
    ├── CloseConversationModal.tsx     # Close dialog with resolution notes
    └── ui/                            # shadcn/ui primitives
```

---

## Setup

### Environment Variables

Create `.env` in the project root (not `backend/`):

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...                          # anon/public key (app client)
SUPABASE_SERVICE_ROLE_KEY=eyJ...             # service role key (RAG client)

# OpenAI
OPENAI_API_KEY=sk-...

# Cohere (for reranking)
COHERE_API_KEY=...

# CORS
CORS_ORIGINS=http://localhost:3000
```

### Supabase Setup

1. The main tables (`conversations`, `tickets`, `scripts_master`, `knowledge_articles`, `kb_lineage`, `learning_events`, `retrieval_corpus`) should already exist from the schema migrations.

2. Run the RPC functions in SQL Editor:
   - `backend/app/rag/db/rpc_functions.sql` — creates `match_corpus()` and `increment_corpus_usage()`
   - `update_corpus_confidence()` — see `backend/HANDOFF_DATABASE.md`

3. Run the schema modifications in SQL Editor:
   - See `backend/HANDOFF_DATABASE.md` — adds `event_type` and `flagged_kb_article_id` to `learning_events`, modifies `retrieval_log` (nullable `ticket_number`, adds `conversation_id`)

### Running

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev    # http://localhost:3000

# Tests (from backend/)
python -m pytest app/rag/tests/ -v

# Seed mock data for testing (from project root)
PYTHONPATH=backend python backend/scripts/seed_mock_data.py
PYTHONPATH=backend python backend/scripts/seed_mock_data.py --clean
```

---

## Key Design Decisions

1. **Conversations and messages are mock data** — loaded from `app/data/` dicts, not from DB. The DB is only used for tickets, corpus, and learning. This is a hackathon constraint.

2. **RAG is a self-contained subsystem** — `app/rag/` has its own models, config, Supabase client, and LLM wrapper. It doesn't import from `app/services/` or `app/schemas/`. The app services call into RAG, not the other way around.

3. **Retrieval logging happens pre-ticket** — When an agent views suggestions, RAG logs are created with `conversation_id` only. The ticket doesn't exist yet. On close, `_link_logs_to_ticket()` stamps the ticket number onto those logs so the learning pipeline can find them.

4. **The learning pipeline is synchronous** — It runs during the close request and blocks the response. This is fine for demo but would need to be async for production.

5. **Two LLM wrappers** — `app/core/llm.py` uses LangChain's `ChatOpenAI` (for ticket generation). `app/rag/core/llm.py` uses the OpenAI SDK directly with instructor-style structured outputs (for RAG nodes). Both read `OPENAI_API_KEY` from env.
