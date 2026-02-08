# INSTRUCTIONS

This file provides guidance to LLMs when working with this repository.

## Project Overview

Hackathon project (hacknation 2026) — **SupportMind**: a self-learning AI support intelligence layer sponsored by RealPage. The system reads customer interactions, extracts operational knowledge, updates institutional memory, and guides both humans and AI agents in real time.

**Core problem:** Support knowledge is fragmented across tickets, scripts/runbooks, and knowledge articles. Complex Tier 3 issues require the right script and correct inputs but agents can't find them quickly. Fixes stay trapped in case notes instead of becoming reusable knowledge.

**Goal:** Build a self-learning support intelligence layer that triages new cases, recommends the best resource (KB article vs. script), updates knowledge with traceability, and enables consistent QA scoring.

## Chosen Feature: Self-Updating Knowledge Engine

Auto-generate and update KB articles from resolved cases and transcripts, with versioning and traceability.

### Self-Learning Loop

```
Resolved Ticket + Conversation
        │
        ▼
   Gap Detection ─────────── "No existing KB match above threshold"
        │                     (Learning_Events.Detected_Gap)
        ▼
   Draft KB Article ────────── Learning_Events.Draft_Summary
        │                      Learning_Events.Proposed_KB_Article_ID -> Knowledge_Articles
        ▼
   Human Review ────────────── Learning_Events.Final_Status (Approved / Rejected)
        │                      Learning_Events.Reviewer_Role
        ▼
   If Approved:
   ├── Publish to Knowledge_Articles (Source_Type = SYNTH_FROM_TICKET)
   ├── Create KB_Lineage records (3 per article):
   │     CREATED_FROM Ticket, CREATED_FROM Conversation, REFERENCES Script
   └── Re-embed into vector DB for future RAG retrieval

   If Rejected:
   └── Discard draft, log rejection reason
```

### Demo Flow

1. **Input:** A resolved Tier 3 ticket (e.g. `CS-38908386`) with its conversation transcript
2. **Gap detection:** System searches existing KB, finds no match above threshold
3. **Draft generation:** LLM extracts structured KB article from ticket resolution + transcript + script
4. **Review UI:** Reviewer sees draft with provenance links, approves or rejects
5. **Publish:** Approved article appears in Knowledge_Articles as `KB-SYN-XXXX`
6. **Verification:** Ask a question from Questions tab — system now retrieves the new article (hit@k improvement)

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2
- **AI/ML:** LangGraph (multi-agent orchestration), OpenAI compatible API (knowledge extraction), pgvector (embeddings)
- **Database:** Supabase (PostgreSQL + pgvector)
- **Frontend:** Next.js
- **Testing:** pytest, pytest-asyncio, httpx (async test client)
- **Linting:** ruff (lint + format), mypy (type checking)

## Architecture

Data flow: Frontend <-> REST API <-> LangGraph Intermediary -> RAG -> DB; Intermediary -> LearningComponent -> RAG/DB

## Dataset — `SupportMind__Final_Data.xlsx`

Single Excel workbook with 11 tabs (synthetic data, no real PII). All dates are Excel serial numbers (days since 1899-12-30). **599 of 999 rows in Conversations/Tickets are blank placeholders — filter on `Status`/`Channel` not empty.**

| Table | Rows | Role |
|---|---|---|
| Conversations | 400 populated / 999 total | Call/chat transcripts (Agent/Customer turns). PK: `Ticket_Number` + `Conversation_ID` |
| Tickets | 400 populated / 999 total | Salesforce-style case records. Joins 1:1 with Conversations on `Ticket_Number` |
| Questions | 1,000 | Ground-truth Q&A for retrieval eval. `Answer_Type` routes to Scripts, KB, or Tickets via `Target_ID` |
| Scripts_Master | 999 | Tier 3 backend data-fix scripts (SQL-like) with `<PLACEHOLDER>` tokens |
| Knowledge_Articles | 3,207 | RAG corpus: 3,046 `SEED_KB` + 161 `SYNTH_FROM_TICKET` |
| Existing_Knowledge_Articles | 3,046 | Seed-only subset with extra metadata for baseline experiments |
| KB_Lineage | 483 populated / 999 total | Provenance: each synthetic article → 3 rows (CREATED_FROM Ticket, CREATED_FROM Conversation, REFERENCES Script) |
| Learning_Events | 161 populated / 999 total | Audit trail: gap detected → draft → approve (134) / reject (27) |
| Placeholder_Dictionary | 25 | Definitions for `<DATABASE>`, `<SITE_NAME>`, `<LEASE_ID>`, etc. |
| QA_Evaluation_Prompt | 1 cell | Rubric for scoring support interactions (interaction QA + case QA, autozero red flags) |

### Key Joins

```
Conversations.Ticket_Number ←→ Tickets.Ticket_Number
Questions.Target_ID → Scripts_Master.Script_ID | Knowledge_Articles.KB_Article_ID | Tickets.Ticket_Number
Tickets.Script_ID → Scripts_Master.Script_ID
Tickets.KB_Article_ID / Generated_KB_Article_ID → Knowledge_Articles.KB_Article_ID
KB_Lineage.KB_Article_ID → Knowledge_Articles; KB_Lineage.Source_ID → Tickets | Conversations | Scripts_Master
Learning_Events.Trigger_Ticket_Number → Tickets; .Proposed_KB_Article_ID → Knowledge_Articles
```

### Categories (across Conversations & Tickets)

General (128), Advance Property Date (118), HAP / Voucher Processing (43), Certifications (38), Move-Out (15), Move-In (14), TRACS File (11), Close Bank Deposit (10), Units / Move-In-Out (7), Gross Rent Change (6), Unit Transfer (5), Waitlist (3), Repayment Plan (1), Security Deposit (1)

## Environment Variables

See `.env.example`. Key settings: `SUPABASE_URL`, `SUPABASE_KEY`, `LLM_API_KEY`, `LLM_MODEL` (default `claude-sonnet-4-5-20250929`), `EMBEDDING_MODEL` (default `text-embedding-3-small`), `EMBEDDING_DIMENSION` (1536), `GAP_SIMILARITY_THRESHOLD` (0.75), `AUTO_PUBLISH_KB` (false).

## Critical Rules

1. **Type hints on every function** — signatures, returns, class attributes. No `Any`.
2. **Pydantic models at all boundaries** — API in/out, LLM responses, DB rows, cross-module calls. Never pass raw dicts.
3. **Single LLM entry point** — all calls through `services/llm.py`. Log tokens and latency on every call.
4. **`temperature=0`** for extraction/classification. `0.3–0.7` only for article drafting.
5. **Never silently swallow exceptions** — log operation, IDs involved, exception type.
6. **Batch vector operations** — never embed one document at a time in a loop.
7. **Immutability** — never mutate function arguments. Return new objects.
8. **No secrets in code** — all config via env vars + pydantic-settings. `.env` in `.gitignore`.
9. **Filter blank rows on load** — 599 placeholder rows must be excluded (check `Status`/`Channel` not empty).
10. **Provenance is mandatory** — every synthetic KB article must have 3 KB_Lineage records.
11. **Files stay small** — 200–400 lines typical, 600 max. Split before it grows.
12. **Absolute imports only** — `from app.services.kb import ...`, never relative.
13. **Test before merge** — `ruff check . && ruff format --check . && mypy app/ && pytest tests/unit/`
