# SupportMind Backend

FastAPI backend serving conversation data, a LangGraph retrieval pipeline, and a learning service that turns resolved tickets into searchable knowledge.

## Project Structure

```
app/
├── main.py                          # FastAPI app, CORS, router registration
├── core/
│   ├── config.py                    # App settings (env vars)
│   └── llm.py                       # LangChain ChatOpenAI (ticket generation)
├── api/
│   ├── conversation_routes.py       # Conversations, close, suggested-actions
│   └── learning_routes.py           # /tickets/{id}/learn, /learning-events/{id}/review
├── schemas/                         # Pydantic models
│   ├── conversations.py, messages.py, tickets.py, learning.py, actions.py
├── services/
│   ├── ticket_service.py            # LLM ticket generation + DB persistence
│   └── learning_service.py          # Learning pipeline
├── db/
│   └── client.py                    # Supabase singleton (anon key)
├── data/                            # Conversation and message data
└── rag/                             # Retrieval subsystem (self-contained)
    ├── core/                        # Config, LLM (OpenAI SDK), embedder, reranker, Supabase client
    ├── agent/                       # LangGraph graphs, node functions, prompts
    ├── models/                      # RagState, CorpusHit, GapDetection, RetrievalLog
    └── tests/                       # Unit tests (test_rag.py, test_nodes.py)
scripts/
├── seed_mock_data.py                # Seed/cleanup sample conversation data for development
├── seed_database.py                 # Full DB seed from Excel + embeddings
└── test_live_pipeline.py            # End-to-end integration test
db/
└── schema.sql                       # Complete DB schema reference
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/conversations` | List all conversations |
| GET | `/api/conversations/{id}` | Get single conversation |
| GET | `/api/conversations/{id}/messages` | Message history |
| GET | `/api/conversations/{id}/suggested-actions` | Retrieval-based suggestions |
| POST | `/api/conversations/{id}/close` | Close + generate ticket + run learning |
| POST | `/api/tickets/{id}/learn` | Manual learning trigger (testing) |
| POST | `/api/learning-events/{id}/review` | Approve/reject KB draft |
| GET | `/` | Health check |

## Retrieval Pipeline

Built with LangGraph. Two graphs share the same node functions.

**QA Graph** (triggered by "Analyze"):
```
plan_query -> retrieve -> rerank -> enrich_sources -> write_answer -> validate -> log_retrieval
                ^                                                        |
                +-------------------- retry (wider search) <-------------+
```
Generates search query variants, embeds them (3072d), searches `retrieval_corpus` via cosine similarity, reranks with Cohere, enriches with source metadata, then writes a cited answer.

**Gap Detection Graph** (triggered on conversation close):
```
plan_query -> retrieve -> rerank -> enrich_sources -> classify_knowledge -> log_retrieval
```
Classifies the ticket's resolution as `SAME_KNOWLEDGE`, `NEW_KNOWLEDGE`, or `CONTRADICTS` relative to existing corpus entries.

## Learning Pipeline

Runs synchronously when a conversation is closed (`learning_service.py`):

1. **Link logs** — stamp `ticket_number` onto retrieval logs created during live support
2. **Score lookups** — set outcomes (RESOLVED/UNHELPFUL) on past retrievals, adjust corpus confidence scores
3. **Gap detection** — run the gap detection graph against the ticket's resolution
4. **Act on result** — CONFIRMED: boost confidence. NEW_KNOWLEDGE: draft KB article (pending review). CONTRADICTS: draft replacement, flag existing article.

## Database Tables

| Table | Purpose |
|-------|---------|
| `conversations` | Customer support conversations (PK: ticket_number) |
| `tickets` | Generated support tickets |
| `scripts_master` | Scripted solutions/procedures |
| `knowledge_articles` | KB articles (seeded + generated) |
| `retrieval_corpus` | Unified vector search index (scripts + KB + ticket resolutions, 3072d embeddings) |
| `retrieval_log` | Retrieval audit trail (query, results, outcomes) |
| `learning_events` | Learning audit (GAP/CONTRADICTION/CONFIRMED events) |
| `kb_lineage` | Provenance chain linking generated articles to source tickets |
| `categories` | 14 support categories |

Full column-level schema: `db/schema.sql`. Detailed documentation: `CLAUDE.md` (project root).

## Architecture Notes

- **Two Supabase clients**: App client (`app/db/client.py`, anon key) and RAG client (`app/rag/core/supabase_client.py`, service role key). Both are thread-safe singletons.
- **Two LLM wrappers**: App uses LangChain ChatOpenAI (ticket generation). RAG uses OpenAI SDK with structured outputs.
- **RAG isolation**: `app/rag/` does not import from `app/services/` or `app/schemas/`. Services call into RAG, not the reverse.
- **Conversation data**: Served from `app/data/`. Tickets, corpus, and learning data use Supabase.

## Testing

```bash
# All unit tests (learning service + RAG, no network needed, <1s)
cd backend && python -m pytest app/services/tests/ app/rag/tests/ -v --tb=short

# Learning service tests only (38 tests)
python -m pytest app/services/tests/test_learning_service.py -v

# RAG tests only (37 tests)
python -m pytest app/rag/tests/ -v

# Live integration test (requires running backend + API keys)
python scripts/test_live_pipeline.py --yes

# Seed sample data for development
PYTHONPATH=backend python scripts/seed_mock_data.py
PYTHONPATH=backend python scripts/seed_mock_data.py --clean
```

On WSL with Windows venv: `backend/.venv/Scripts/python.exe -m pytest ...`

## Environment Variables

Create `.env` in the **project root** (not `backend/`):

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...                    # anon/public key
SUPABASE_SERVICE_ROLE_KEY=eyJ...       # service role key (RAG)
OPENAI_API_KEY=sk-...                  # GPT-4o-mini + embeddings
COHERE_API_KEY=...                     # Cohere reranker
CORS_ORIGINS=http://localhost:3000
```