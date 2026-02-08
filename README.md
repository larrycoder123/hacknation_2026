# SupportMind — Self-Learning Support Intelligence

**Hack-Nation 2026 | RealPage Sponsor Track**

Most support AI is a static lookup — it searches a fixed knowledge base and returns canned answers. SupportMind closes the loop: every resolved ticket teaches the system something new, so the knowledge base grows and self-corrects with use. Agents get better suggestions over time without anyone manually writing articles.

## How It Works

1. **Agent clicks "Analyze"** — a RAG pipeline searches scripts, KB articles, and past ticket resolutions, reranked by confidence and relevance
2. **Agent resolves the issue** — using suggested actions as guidance
3. **System generates a structured ticket** — LLM extracts root cause, resolution, and tags automatically on close
4. **Gap detection runs** — the resolution is classified against existing knowledge: *confirmed*, *new knowledge*, or *contradicts* an existing article
5. **Reviewer approves or rejects** — approved KB drafts are embedded into the corpus; the next search already includes them

The result: a support system where resolved ticket #500 makes ticket #501 easier to solve.

## What Sets It Apart

- **Confidence scoring** — every retrieval adjusts the source's confidence. Helpful articles surface higher; unhelpful ones decay. No manual curation needed.
- **Contradiction detection** — when a ticket resolution conflicts with an existing KB article, the system flags it and drafts a replacement. Stale runbooks don't silently rot.
- **Knowledge traceability** — every AI-generated article traces back to its source tickets and conversations through `kb_lineage`. Nothing is a black box.
- **Unified vector corpus** — scripts, KB articles, and ticket resolutions share a single 3072-dimensional index. One search covers everything.

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, React 19, TypeScript, TailwindCSS 4, Shadcn/ui |
| Backend | FastAPI, Python 3.12+, Pydantic 2.9+ |
| Database | Supabase PostgreSQL 17 + pgvector |
| AI / RAG | LangGraph, OpenAI GPT-4o-mini, text-embedding-3-large (3072d), Cohere rerank-v4.0-pro |

## Quick Start

**Prerequisites:** Python 3.12+, Node 20+, a `.env` file in the project root (see [backend/README.md](backend/README.md#environment-variables) for required variables).

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev    # http://localhost:3000
```

## Project Structure

```
backend/    FastAPI app, RAG pipeline, self-learning service
frontend/   Next.js agent workspace + learning review UI
CLAUDE.md   Detailed specs (schema, API, pipeline internals)
```

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for subsystem details.

## Testing

```bash
# Unit tests (no network required, <1s)
cd backend && python -m pytest app/services/tests/ app/rag/tests/ -v --tb=short

# Live integration test (requires running backend + API keys)
python backend/scripts/test_live_pipeline.py --yes
```

See [backend/README.md](backend/README.md#testing) for the full test matrix.

## Architecture

```
Frontend (Next.js)  ──HTTP──>  Backend (FastAPI)  ──>  Supabase (Postgres + pgvector)
                                  ├─ Services             OpenAI (GPT-4o-mini + embeddings)
                                  └─ RAG (LangGraph)      Cohere (reranking)
```
