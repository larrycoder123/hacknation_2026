# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hackathon project (hacknation 2026) — **SupportMind**: a self-learning AI support intelligence layer sponsored by RealPage. The system continuously reads customer interactions, extracts operational knowledge, updates institutional memory, and guides both humans and AI agents in real time.

**Core problem:** Support knowledge is fragmented across tickets, scripts/runbooks, and knowledge articles. Complex Tier 3 issues require the right script and correct inputs but agents can't find them quickly. Fixes stay trapped in case notes instead of becoming reusable knowledge. QA/coaching are manual and inconsistent.

**Goal:** Build a self-learning support intelligence layer that triages new cases, recommends the best resource (KB article vs. script), updates knowledge with traceability, and enables consistent QA scoring.

## Chosen Feature: Self-Updating Knowledge Engine

Auto-generate and update KB articles from resolved cases and transcripts, with versioning and traceability.

### What It Does

A closed-loop learning pipeline that:
1. **Detects knowledge gaps** — when a resolved ticket/conversation has no matching KB article above a similarity threshold
2. **Drafts new KB articles** — extracts resolution steps, root cause, and context from the ticket + transcript + script into a structured article
3. **Routes for human review** — Tier 3 Support or Support Ops Review approves/rejects the draft
4. **Publishes approved articles** — inserts into the Knowledge_Articles corpus with full provenance (KB_Lineage tracing back to source ticket, conversation, and script)
5. **Updates the vector index** — newly published articles become immediately retrievable by the RAG pipeline

### Self-Learning Loop (maps directly to dataset)

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

### Key Dataset Tables for This Feature

| Table | Role in Self-Learning | Rows |
|---|---|---|
| Conversations | Source transcripts to extract knowledge from | 400 populated |
| Tickets | Resolved cases with Description, Resolution, Root_Cause | 400 populated |
| Scripts_Master | Backend fix scripts referenced in resolutions | 999 |
| Knowledge_Articles | Target corpus — seed (3,046) + synthetic from tickets (161) | 3,207 |
| KB_Lineage | Provenance chain: article -> ticket/conversation/script | 483 populated |
| Learning_Events | Audit trail: gap detected -> draft -> approve/reject | 161 populated (134 approved, 27 rejected) |
| Questions | Ground-truth for evaluating retrieval after KB updates | 1,000 |

### Demo Flow

1. **Input:** A resolved Tier 3 ticket (e.g. `CS-38908386`) with its conversation transcript
2. **Gap detection:** System searches existing KB, finds no match above threshold
3. **Draft generation:** LLM extracts structured KB article from ticket resolution + transcript + script
4. **Review UI:** Reviewer sees draft with provenance links, approves or rejects
5. **Publish:** Approved article appears in Knowledge_Articles as `KB-SYN-XXXX`
6. **Verification:** Ask a question from Questions tab — system now retrieves the new article (hit@k improvement)

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2
- **AI/ML:** LangGraph (multi-agent orchestration), Claude/GPT API (knowledge extraction), pgvector (embeddings)
- **Database:** Supabase (PostgreSQL + pgvector)
- **Frontend:** TBD
- **Testing:** pytest, pytest-asyncio, httpx (async test client)
- **Linting:** ruff (lint + format), mypy (type checking)
- **IDE:** IntelliJ IDEA (JDK 24)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (TBD)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  routers/ -> services/ -> agents/ -> db/                    │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Supabase │   │ LLM API  │   │ pgvector │
        │ Postgres │   │ (Claude) │   │ embeddings│
        └──────────┘   └──────────┘   └──────────┘
```

Data flow: Frontend <-> REST API <-> LangGraph Intermediary -> RAG -> DB; Intermediary -> LearningComponent -> RAG/DB

---

## Dataset — `SupportMind__Final_Data.xlsx`

Single Excel workbook with 11 tabs (synthetic data, no real PII). All dates are Excel serial numbers. Timestamps like `45705.337` = Excel date serial (days since 1899-12-30).

---

### 1. Conversations (999 rows)

Call/chat transcripts with agent and customer turns.

| Column | Type | Description | Example |
|---|---|---|---|
| `Ticket_Number` | string (PK) | Case ID | `CS-38908386` |
| `Conversation_ID` | string (PK) | Conversation ID | `CONV-O2RAK1VRJN` |
| `Channel` | enum | `Chat` (225), `Phone` (175), blank (599) | `Chat` |
| `Conversation_Start` | float | Excel date serial | `45705.337` |
| `Conversation_End` | float | Excel date serial | `45705.356` |
| `Customer_Role` | string | Role of the caller | `Accounting Clerk` |
| `Agent_Name` | string | Support agent first name | `Alex` |
| `Product` | string | Always `ExampleCo PropertySuite Affordable` (400 populated) | |
| `Category` | string | Issue category (see below) | `Advance Property Date` |
| `Issue_Summary` | string | One-line summary | |
| `Transcript` | text | Full multi-turn transcript (`Agent:` / `Customer:` lines) | |
| `Sentiment` | enum | `Neutral` (140), `Relieved` (134), `Curious` (78), `Frustrated` (48) | |
| `Generation_Source_Record` | string | Script ID used to generate this record | `SCRIPT-0040` |

**Note:** 599 rows are blank placeholder rows (only `Ticket_Number` populated). 400 rows have full data.

**Categories** (across Conversations & Tickets): General (128), Advance Property Date (118), HAP / Voucher Processing (43), Certifications (38), Move-Out (15), Move-In (14), TRACS File (11), Close Bank Deposit (10), Units / Move-In-Out (7), Gross Rent Change (6), Unit Transfer (5), Waitlist (3), Repayment Plan (1), Security Deposit (1)

---

### 2. Tickets (999 rows)

Salesforce-style case records. Joins 1:1 with Conversations on `Ticket_Number`.

| Column | Type | Description | Example |
|---|---|---|---|
| `Ticket_Number` | string (PK) | | `CS-38908386` |
| `Conversation_ID` | string (FK) | | `CONV-O2RAK1VRJN` |
| `Created_At` | float | Excel date serial | `45705.337` |
| `Closed_At` | float | Excel date serial | `45706.087` |
| `Status` | enum | `Closed` (400), blank (599) | |
| `Priority` | enum | `Medium` (146), `High` (137), `Low` (67), `Critical` (50) | |
| `Tier` | enum | `3.0` (161), `1.0` (121), `2.0` (118) | |
| `Product` | string | `ExampleCo PropertySuite Affordable` | |
| `Module` | string | E.g. `Accounting / Date Advance`, `Compliance / Certifications` | |
| `Category` | string | Same categories as Conversations | |
| `Case_Type` | enum | `Incident` (249), `How-To` (82), `Training` (69) | |
| `Account_Name` | string | Synthetic company name | `Oak & Ivy Management` |
| `Property_Name` | string | Synthetic property name | `Heritage Point` |
| `Property_City` | string | | `Minneapolis` |
| `Property_State` | string | 2-letter state | `MN` |
| `Contact_Name` | string | Synthetic contact | `Morgan Johnson` |
| `Contact_Role` | string | | `Accounting Clerk` |
| `Contact_Email` | string | Synthetic (`@pmc-example.com`) | `morgan.johnson@pmc-example.com` |
| `Contact_Phone` | string | Synthetic (`555-xxx`) | `(555) 567-6635` |
| `Subject` | string | Ticket subject line | `Unable to advance property date (backend data sync)` |
| `Description` | text | Full problem description | |
| `Resolution` | text | Resolution notes | |
| `Root_Cause` | string | | `Data inconsistency requiring backend fix` |
| `Tags` | string | Comma-separated | `PropertySuite, affordable, date-advance, month-end` |
| `KB_Article_ID` | string (FK) | Linked KB article | `KB-D448538B4F` |
| `Generation_Source_Record` | string | | `SCRIPT-0040` |
| `Script_ID` | string (FK) | Script used to resolve | `SCRIPT-0293` |
| `Generated_KB_Article_ID` | string (FK) | KB article generated from this ticket | `KB-SYN-0001` |

---

### 3. Questions (1,000 rows)

Ground-truth Q&A pairs for retrieval evaluation.

| Column | Type | Description | Example |
|---|---|---|---|
| `Question_ID` | string (PK) | | `Q-0001` |
| `Source` | enum | `Scripts` (700), `AFF Data` (300) | |
| `Product` | string | `ExampleCo PropertySuite Affordable` | |
| `Category` | string | Issue category | `Certifications` |
| `Module` | string | | `Compliance / Certifications` |
| `Difficulty` | enum | `Hard` (605), `Easy` (282), `Medium` (113) | |
| `Question_Text` | text | Full customer question | |
| `Answer_Type` | enum | **`SCRIPT`** (700), **`KB`** (209), **`TICKET_RESOLUTION`** (91) | |
| `Target_ID` | string (FK) | Points to `Script_ID`, `KB_Article_ID`, or `Ticket_Number` based on `Answer_Type` | `SCRIPT-0142` |
| `Target_Title` | string | Title of the target resource | |
| `Generation_Source_Record` | string | | `SCRIPT-0354` |

**Routing logic:** `Answer_Type=SCRIPT` -> `Scripts_Master.Script_ID` | `Answer_Type=KB` -> `Knowledge_Articles.KB_Article_ID` | `Answer_Type=TICKET_RESOLUTION` -> `Tickets.Ticket_Number`

---

### 4. Scripts_Master (999 rows)

Canonical Tier 3 backend data-fix scripts (SQL-like) with sanitized placeholders.

| Column | Type | Description | Example |
|---|---|---|---|
| `Script_ID` | string (PK) | | `SCRIPT-0001` |
| `Script_Title` | string | | `Compliance / Certifications` |
| `Script_Purpose` | string | What the script does | `Run this backend data-fix script to resolve a Certifications issue...` |
| `Script_Inputs` | string | Comma-separated placeholders required | `<DATABASE>, <SITE_NAME>` |
| `Module` | string | | `Compliance / Certifications` |
| `Category` | string | | `Certifications` |
| `Source` | string | | `Questions` |
| `Script_Text_Sanitized` | text | Full SQL script with placeholders | `use <DATABASE>\ngo\n\nupdate demographicsetting set...` |

---

### 5. Placeholder_Dictionary (25 rows)

Definitions for all `<PLACEHOLDER>` tokens used in scripts and KB articles.

| Column | Type | Example |
|---|---|---|
| `Placeholder` | string | `<LEASE_ID>`, `<DATABASE>`, `<AMOUNT>`, `<SITE_NAME>` |
| `Meaning` | string | `Currency/amount value` |
| `Example` | string | `set amount = <AMOUNT>` |

All 25 placeholders: `<AMOUNT>`, `<CERTIFICATION_ID>`, `<CUSTOMER_NAME>`, `<DATABASE>`, `<DATE>`, `<DATETIME>`, `<ID>`, `<LEASE_ID>`, `<NAME>`, `<PHONE>`, `<PROPERTY_NAME>`, `<SITE_NAME>`, `<SUPPORT_EMAIL>`, `<TEXT>`, `<URL>`, and others.

---

### 6. Knowledge_Articles (3,207 rows)

Combined RAG corpus — seed KB articles plus synthetic articles generated from Tier 3 cases.

| Column | Type | Description | Example |
|---|---|---|---|
| `KB_Article_ID` | string (PK) | Seed: `KB-{hex}`, Synthetic: `KB-SYN-####` | `KB-3FFBFE3C70` |
| `Title` | string | Article title | `PropertySuite Facilities (New): Editing Time Worked` |
| `Body` | text | Full article content | |
| `Tags` | string | (populated on synthetic articles) | |
| `Module` | string | (populated on synthetic articles) | |
| `Category` | string | (populated on synthetic articles) | |
| `Created_At` | float | (populated on synthetic articles) | |
| `Updated_At` | float | (populated on synthetic articles) | |
| `Status` | enum | Always `Active` (3,207) | |
| `Source_Type` | enum | **`SEED_KB`** (3,046) or **`SYNTH_FROM_TICKET`** (161) | |

---

### 7. Existing_Knowledge_Articles (3,046 rows)

Seed-only subset for baseline RAG experiments. Same articles as `SEED_KB` rows in Knowledge_Articles but with extra metadata.

| Column | Type | Description | Example |
|---|---|---|---|
| `KB_Article_ID` | string (PK) | | `KB-3FFBFE3C70` |
| `Source_PK` | string | Original source system PK | `1.83210541E8` |
| `Title` | string | | |
| `URL` | string | Always `<URL_REDACTED>` | |
| `Body` | text | Full article content | |
| `Product` | string | | `Affordable` |
| `Experience` | string | | `New` |
| `Source_Table` | string | | `salesforce_kas` |
| `Source_Type` | enum | Always `SEED_KB` | |

---

### 8. KB_Lineage (999 rows)

Provenance chain: links synthetic KB articles back to their source tickets, conversations, and scripts.

| Column | Type | Description | Example |
|---|---|---|---|
| `KB_Article_ID` | string (FK) | | `KB-SYN-0001` |
| `Source_Type` | enum | `Ticket` (161), `Conversation` (161), `Script` (161) | |
| `Source_ID` | string (FK) | Points to `Ticket_Number`, `Conversation_ID`, or `Script_ID` | `CS-38908386` |
| `Relationship` | enum | `CREATED_FROM` (322), `REFERENCES` (161) | |
| `Evidence_Snippet` | string | Human-readable provenance text | |
| `Event_Timestamp` | float | Excel date serial | |

**Pattern:** Each synthetic KB article has 3 lineage rows: CREATED_FROM Ticket, CREATED_FROM Conversation, REFERENCES Script.

---

### 9. Learning_Events (999 rows)

Simulated self-learning workflow: gap detected -> KB drafted -> human review decision.

| Column | Type | Description | Example |
|---|---|---|---|
| `Event_ID` | string (PK) | | `LEARN-0001` |
| `Trigger_Ticket_Number` | string (FK) | | `CS-38908386` |
| `Trigger_Conversation_ID` | string (FK) | | `CONV-O2RAK1VRJN` |
| `Detected_Gap` | string | What gap was found | `No existing KB match above threshold for Advance Property Date issue` |
| `Proposed_KB_Article_ID` | string (FK) | | `KB-SYN-0001` |
| `Draft_Summary` | string | | `Draft KB created to document backend resolution steps for...` |
| `Final_Status` | enum | **`Approved`** (134), **`Rejected`** (27), blank (838) | |
| `Reviewer_Role` | enum | `Tier 3 Support` (134), `Support Ops Review` (27) | |
| `Event_Timestamp` | float | Excel date serial | |

**Note:** Only 161 rows have full data. Approved events -> KB article gets published. Rejected events -> draft discarded.

---

### 10. QA_Evaluation_Prompt (single-cell rubric)

Not tabular data — contains a structured QA rubric prompt for scoring support interactions. Key details:

- **Scoring modes:** Interaction-only (100%), Case-only (100%), or Both (70% interaction + 30% case)
- **Interaction QA** (10 params, 10% each): Customer Delight (5 params) + Resolution Handling (5 params)
- **Case QA** (10 params, 10% each): Documentation Quality (5 params) + Resolution Quality (5 params)
- **Autozero rules:** If `Delivered_Expected_Outcome = No` -> Interaction score = 0%. If any Red Flag = Yes -> Overall = 0%
- **Red Flags:** Account Documentation Violation, PCI Violation, Data Integrity Violation, Misbehavior
- **Output format:** Structured JSON with per-parameter scores, tracking items (verbatim from library), evidence quotes

---

### Key Join Fields

```
Conversations.Ticket_Number ──────── Tickets.Ticket_Number
Conversations.Conversation_ID ───── Tickets.Conversation_ID

Questions.Target_ID ──┬── Scripts_Master.Script_ID      (when Answer_Type = SCRIPT)
                      ├── Knowledge_Articles.KB_Article_ID (when Answer_Type = KB)
                      └── Tickets.Ticket_Number          (when Answer_Type = TICKET_RESOLUTION)

Tickets.Script_ID ─────────────────── Scripts_Master.Script_ID
Tickets.KB_Article_ID ─────────────── Knowledge_Articles.KB_Article_ID
Tickets.Generated_KB_Article_ID ───── Knowledge_Articles.KB_Article_ID

KB_Lineage.KB_Article_ID ─────────── Knowledge_Articles.KB_Article_ID
KB_Lineage.Source_ID ──┬────────────── Tickets.Ticket_Number       (Source_Type = Ticket)
                       ├────────────── Conversations.Conversation_ID (Source_Type = Conversation)
                       └────────────── Scripts_Master.Script_ID      (Source_Type = Script)

Learning_Events.Trigger_Ticket_Number ─── Tickets.Ticket_Number
Learning_Events.Trigger_Conversation_ID ── Conversations.Conversation_ID
Learning_Events.Proposed_KB_Article_ID ─── Knowledge_Articles.KB_Article_ID
```

### Evaluation Approach

- **Retrieval accuracy:** `Questions.Answer_Type` + `Target_ID` as ground truth (hit@k / exact-match ID)
- **Provenance / traceability:** KB_Lineage validates article-to-ticket/transcript/script lineage
- **Agent QA:** QA_Evaluation_Prompt scores transcript and ticket quality (weighted scoring; autozero red flags)
- **Self-learning loop:** Learning_Events + Generated_KB_Article_ID demonstrate propose -> review -> publish cycle

## Evaluation Criteria

| Criterion | What Success Looks Like |
|---|---|
| Learning Capability | System improves knowledge automatically from conversations |
| Compliance & Safety | Detects policy violations or risky guidance |
| Accuracy & Consistency | Responses align with updated knowledge |
| Automation & Scalability | Handles thousands of conversations |
| Clarity of Demo | Input -> AI analysis -> knowledge update + coaching |
| Enterprise Readiness | Fits real support workflows |

## File Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory, startup/shutdown, CORS
│   ├── config.py            # pydantic-settings BaseSettings (env vars)
│   ├── exceptions.py        # SupportMindError hierarchy + exception handlers
│   ├── models/              # Pydantic schemas
│   │   ├── tickets.py       # Ticket, Conversation domain models
│   │   ├── kb.py            # KBArticle, KBDraft, KBLineage models
│   │   ├── learning.py      # LearningEvent, GapDetection models
│   │   └── api.py           # ApiResponse[T] generic wrapper
│   ├── routers/             # One router per domain
│   │   ├── tickets.py       # /api/tickets
│   │   ├── kb.py            # /api/kb
│   │   └── learning.py      # /api/learning
│   ├── services/            # Business logic (no HTTP, no framework deps)
│   │   ├── gap_detection.py # Vector similarity search for knowledge gaps
│   │   ├── draft_generator.py # LLM-based KB article drafting
│   │   ├── review.py        # Approve/reject workflow
│   │   ├── publisher.py     # Publish KB + lineage + re-embed
│   │   └── llm.py           # Single LLM wrapper (all calls go through here)
│   ├── agents/              # LangGraph graph definitions
│   │   ├── learning_loop.py # Full gap->draft->review->publish graph
│   │   └── prompts/         # Prompt templates (versioned constants)
│   ├── db/                  # Database layer
│   │   ├── supabase.py      # Client factory, connection management
│   │   └── vectors.py       # Embedding operations (batch upsert, search)
│   └── utils/               # Pure helpers
│       ├── dates.py         # Excel serial -> datetime conversion
│       └── text.py          # Transcript parsing, sanitization
├── tests/
│   ├── unit/                # Pure logic (mock DB + LLM)
│   ├── integration/         # Real DB, full learning loop
│   └── conftest.py          # Shared fixtures (dataset rows)
├── data/
│   ├── loader.py            # xlsx -> typed Pydantic models
│   └── SupportMind__Final_Data.xlsx
├── pyproject.toml           # Deps, ruff config, pytest config
└── .env.example             # Template (never commit .env)
```

---

## Build & Run Commands

```bash
# Setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in real values

# Run dev server
uvicorn app.main:app --reload --port 8000

# Lint & format
ruff check .
ruff format .
mypy app/

# Run all tests
pytest

# Run unit tests only (fast, no network)
pytest tests/unit/ -v

# Run a single test file
pytest tests/unit/test_gap_detection.py -v

# Run a single test by name
pytest tests/unit/test_gap_detection.py -k "test_detects_gap_when_no_match" -v

# Run with coverage
pytest --cov=app --cov-report=html

# Pre-commit check (run before every commit)
ruff check . && ruff format --check . && mypy app/ && pytest tests/unit/
```

---

## Code Patterns

### API Response Wrapper

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None

    @classmethod
    def ok(cls, data: T) -> "ApiResponse[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ApiResponse[T]":
        return cls(success=False, error=error)
```

### Domain Models (Pydantic v2)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import StrEnum

class SourceType(StrEnum):
    SEED_KB = "SEED_KB"
    SYNTH_FROM_TICKET = "SYNTH_FROM_TICKET"

class KBArticle(BaseModel):
    kb_article_id: str = Field(pattern=r"^KB-(SYN-\d{4}|[A-Fa-f0-9]{10})$")
    title: str
    body: str
    tags: str = ""
    module: str = ""
    category: str = ""
    status: str = "Active"
    source_type: SourceType
    created_at: datetime | None = None
    updated_at: datetime | None = None

class ReviewDecision(StrEnum):
    APPROVED = "Approved"
    REJECTED = "Rejected"

class LearningEvent(BaseModel):
    event_id: str
    trigger_ticket_number: str
    trigger_conversation_id: str
    detected_gap: str
    proposed_kb_article_id: str
    draft_summary: str
    final_status: ReviewDecision | None = None
    reviewer_role: str | None = None
    event_timestamp: datetime | None = None
```

### Router Pattern (FastAPI)

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/learning", tags=["learning"])

@router.post("/detect-gap", response_model=ApiResponse[LearningEvent])
async def detect_gap(
    ticket_number: str,
    gap_service: GapDetectionService = Depends(get_gap_service),
) -> ApiResponse[LearningEvent]:
    event = await gap_service.detect(ticket_number)
    if event is None:
        return ApiResponse.ok(None)
    return ApiResponse.ok(event)

@router.post("/review/{event_id}", response_model=ApiResponse[KBArticle])
async def review_draft(
    event_id: str,
    decision: ReviewDecision,
    review_service: ReviewService = Depends(get_review_service),
) -> ApiResponse[KBArticle]:
    result = await review_service.decide(event_id, decision)
    return ApiResponse.ok(result)
```

### LLM Wrapper (single entry point)

```python
import logging
import time
from typing import TypeVar
from anthropic import AsyncAnthropic
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def call_llm_structured(
    prompt: str,
    response_model: type[T],
    settings: Settings,
    temperature: float = 0.0,
) -> T:
    client = AsyncAnthropic(api_key=settings.llm_api_key)
    start = time.monotonic()

    response = await client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
        tools=[{
            "name": "structured_output",
            "description": "Return structured data",
            "input_schema": response_model.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "structured_output"},
    )

    latency_ms = (time.monotonic() - start) * 1000
    logger.info(
        "LLM call: model=%s input_tokens=%d output_tokens=%d latency=%.0fms",
        settings.llm_model,
        response.usage.input_tokens,
        response.usage.output_tokens,
        latency_ms,
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    return response_model.model_validate(tool_use.input)
```

### LangGraph Agent State

```python
from typing import TypedDict, NotRequired
from app.models.kb import KBArticle, KBDraft
from app.models.learning import LearningEvent, ReviewDecision

class LearningLoopState(TypedDict):
    ticket_number: str
    conversation_id: str
    gap_detected: bool
    similarity_score: float
    draft: NotRequired[KBDraft]
    review_decision: NotRequired[ReviewDecision]
    published_article: NotRequired[KBArticle]
    error: NotRequired[str]
```

### Exception Hierarchy

```python
class SupportMindError(Exception):
    """Base for all application errors."""

class ArticleNotFoundError(SupportMindError):
    """KB article ID does not exist."""

class DuplicateArticleError(SupportMindError):
    """KB article with this ID already exists."""

class GapDetectionError(SupportMindError):
    """Vector search failed during gap detection."""

class LLMParseError(SupportMindError):
    """LLM returned unparseable output after retries."""

# In main.py:
@app.exception_handler(ArticleNotFoundError)
async def handle_not_found(request, exc):
    return JSONResponse(status_code=404, content=ApiResponse.fail(str(exc)).model_dump())

@app.exception_handler(DuplicateArticleError)
async def handle_conflict(request, exc):
    return JSONResponse(status_code=409, content=ApiResponse.fail(str(exc)).model_dump())
```

### Data Loader

```python
from datetime import datetime, timedelta
from functools import lru_cache
import openpyxl
from app.models.tickets import Ticket, Conversation

EXCEL_EPOCH = datetime(1899, 12, 30)
TICKET_COLUMNS = [
    "Ticket_Number", "Conversation_ID", "Created_At", "Closed_At", "Status",
    "Priority", "Tier", "Product", "Module", "Category", "Case_Type",
    "Account_Name", "Property_Name", "Property_City", "Property_State",
    "Contact_Name", "Contact_Role", "Contact_Email", "Contact_Phone",
    "Subject", "Description", "Resolution", "Root_Cause", "Tags",
    "KB_Article_ID", "Generation_Source_Record", "Script_ID",
    "Generated_KB_Article_ID",
]

def excel_serial_to_datetime(serial: float | None) -> datetime | None:
    if serial is None:
        return None
    return EXCEL_EPOCH + timedelta(days=serial)

@lru_cache(maxsize=1)
def load_tickets(xlsx_path: str) -> list[Ticket]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb["Tickets"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    status_idx = TICKET_COLUMNS.index("Status")
    return [
        Ticket.model_validate(dict(zip(TICKET_COLUMNS, row)))
        for row in rows
        if row[status_idx]  # Filter 599 blank placeholder rows
    ]
```

---

## Testing

### Running Tests

```bash
pytest                                    # all tests
pytest tests/unit/ -v                     # unit only
pytest tests/integration/ -v             # integration only
pytest -k "gap_detection" -v              # by keyword
pytest --cov=app --cov-report=term-missing  # with coverage
```

### Test Structure

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

@pytest.fixture
def sample_ticket() -> dict:
    """Real row from SupportMind__Final_Data.xlsx for deterministic tests."""
    return {
        "ticket_number": "CS-38908386",
        "conversation_id": "CONV-O2RAK1VRJN",
        "category": "Advance Property Date",
        "tier": 3,
        "resolution": "Applied backend data-fix script. Customer confirmed.",
        "script_id": "SCRIPT-0293",
    }

@pytest.mark.asyncio
async def test_detect_gap_returns_event(client: AsyncClient, sample_ticket):
    response = await client.post(
        "/api/learning/detect-gap",
        params={"ticket_number": sample_ticket["ticket_number"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["detected_gap"] is not None

@pytest.mark.asyncio
async def test_detect_gap_returns_none_when_kb_exists(client: AsyncClient):
    response = await client.post(
        "/api/learning/detect-gap",
        params={"ticket_number": "CS-ALREADY-COVERED"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None

@pytest.mark.asyncio
async def test_review_reject_does_not_publish(client: AsyncClient):
    response = await client.post(
        "/api/learning/review/LEARN-0003",
        params={"decision": "Rejected"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] is None  # Rejected drafts are discarded, no article published
```

---

## Configuration

### Environment Variables

```bash
# .env.example

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# LLM
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-5-20250929
LLM_MAX_RETRIES=3

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Self-learning thresholds
GAP_SIMILARITY_THRESHOLD=0.75
AUTO_PUBLISH_KB=false

# Server
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### Settings Class

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    llm_api_key: str
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_max_retries: int = 3
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    gap_similarity_threshold: float = 0.75
    auto_publish_kb: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

---

## Critical Rules

1. **Type hints on every function** -- signatures, returns, class attributes. No `Any`.
2. **Pydantic models at all boundaries** -- API in/out, LLM responses, DB rows, cross-module calls. Never pass raw dicts.
3. **Single LLM entry point** -- all calls through `services/llm.py`. Log tokens and latency on every call.
4. **`temperature=0`** for extraction/classification. `0.3-0.7` only for article drafting.
5. **Never silently swallow exceptions** -- log operation, IDs involved, exception type.
6. **Batch vector operations** -- never embed one document at a time in a loop.
7. **Immutability** -- never mutate function arguments. Return new objects.
8. **No secrets in code** -- all config via env vars + pydantic-settings. `.env` in `.gitignore`.
9. **Filter blank rows on load** -- 599 placeholder rows in Conversations/Tickets must be excluded (check `Status`/`Channel` not empty).
10. **Provenance is mandatory** -- every synthetic KB article must have 3 KB_Lineage records (CREATED_FROM Ticket, CREATED_FROM Conversation, REFERENCES Script).
11. **Files stay small** -- 200-400 lines typical, 600 max. Split before it grows.
12. **Absolute imports only** -- `from app.services.kb import ...`, never `from ..services`.
13. **Test before merge** -- `ruff check . && ruff format --check . && mypy app/ && pytest tests/unit/`.