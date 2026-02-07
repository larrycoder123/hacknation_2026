-- 001: Create Tables (12 tables, ordered by dependency)

create extension if not exists vector with schema extensions;

------------------------------------------------------------------------
-- LOOKUPS & CONFIG
------------------------------------------------------------------------

-- Issue categories shared across scripts, KB, conversations, tickets, questions
create table categories (
    name            text primary key
);

-- What each <PLACEHOLDER> token means in scripts (e.g. <DATABASE>, <LEASE_ID>)
create table placeholder_dictionary (
    placeholder     text primary key,
    meaning         text,
    example         text
);

-- App settings (thresholds, feature flags)
create table config (
    key             text primary key,
    value           jsonb not null default '{}'::jsonb
);

------------------------------------------------------------------------
-- CORE DOMAIN
------------------------------------------------------------------------

-- Tier 3 backend data-fix scripts (999 rows, most common answer source)
create table scripts_master (
    script_id             text primary key,
    script_title          text,
    script_purpose        text,
    module                text,
    category              text references categories (name),
    source                text check (source in ('Questions', 'Tickets')),
    script_text_sanitized text              -- SQL with <PLACEHOLDER> tokens
);

-- KB articles: 3,046 seed (imported) + 161 synthetic (from learning loop)
create table knowledge_articles (
    kb_article_id   text primary key,       -- seed: KB-{hex}, synthetic: KB-SYN-####
    title           text,
    body            text,
    tags            text,
    module          text,
    category        text references categories (name),
    created_at      timestamptz,
    updated_at      timestamptz,
    status          text default 'Active' check (status in ('Active', 'Draft', 'Archived')),
    source_type     text not null check (source_type in ('SEED_KB', 'SYNTH_FROM_TICKET'))
);

-- Agent/customer transcripts. 400 populated out of 999 (filter blanks on load).
-- Tickets join here via ticket_number; shared fields (product, category) live here.
create table conversations (
    ticket_number         text primary key,
    conversation_id       text unique,
    channel               text check (channel in ('Chat', 'Phone') or channel is null),
    conversation_start    timestamptz,
    conversation_end      timestamptz,
    customer_role         text,
    agent_name            text,
    product               text,
    category              text references categories (name),
    issue_summary         text,
    transcript            text,             -- full Agent:/Customer: turns
    sentiment             text check (sentiment in ('Neutral', 'Relieved', 'Curious', 'Frustrated') or sentiment is null),
    generation_source_record text
);

------------------------------------------------------------------------
-- JOINS & EXTENSIONS
------------------------------------------------------------------------

-- Which placeholders each script requires (replaces comma-separated column)
create table script_placeholders (
    script_id       text not null references scripts_master (script_id),
    placeholder     text not null references placeholder_dictionary (placeholder),
    primary key (script_id, placeholder)
);

-- Support cases, 1:1 with conversations via ticket_number
create table tickets (
    ticket_number   text primary key references conversations (ticket_number),
    created_at      timestamptz,
    closed_at       timestamptz,
    status          text check (status in ('Open', 'Closed', 'Pending') or status is null),
    priority        text check (priority in ('Critical', 'High', 'Medium', 'Low') or priority is null),
    tier            text check (tier in ('1', '2', '3') or tier is null),
    module          text,
    case_type       text check (case_type in ('Incident', 'How-To', 'Training') or case_type is null),
    subject         text,
    description     text,
    resolution      text,
    root_cause      text,
    tags            text,
    kb_article_id   text references knowledge_articles (kb_article_id),
    script_id       text references scripts_master (script_id),
    generated_kb_article_id text references knowledge_articles (kb_article_id)
);

------------------------------------------------------------------------
-- WORKFLOW & AUDIT
------------------------------------------------------------------------

-- Traces each synthetic KB article back to its source ticket/conversation/script
-- (3 rows per synthetic article: 2x CREATED_FROM + 1x REFERENCES)
create table kb_lineage (
    kb_article_id   text not null references knowledge_articles (kb_article_id),
    source_type     text not null check (source_type in ('Ticket', 'Conversation', 'Script')),
    source_id       text not null,
    relationship    text not null check (relationship in ('CREATED_FROM', 'REFERENCES')),
    evidence_snippet text,
    event_timestamp timestamptz,
    primary key (kb_article_id, source_type, source_id)
);

-- Learning loop audit: gap detected -> KB drafted -> human approves/rejects
-- (134 approved, 27 rejected in dataset)
create table learning_events (
    event_id                text primary key,
    trigger_ticket_number   text references tickets (ticket_number),
    detected_gap            text,
    proposed_kb_article_id  text references knowledge_articles (kb_article_id),
    draft_summary           text,
    final_status            text check (final_status in ('Approved', 'Rejected') or final_status is null),
    reviewer_role           text check (reviewer_role in ('Tier 3 Support', 'Support Ops Review') or reviewer_role is null),
    event_timestamp         timestamptz
);

------------------------------------------------------------------------
-- SEARCH & EVALUATION
------------------------------------------------------------------------

-- 1,000 test questions with known answers for measuring retrieval accuracy
-- answer_type -> target_id points to: scripts_master / knowledge_articles / tickets
create table questions (
    question_id     text primary key,
    source          text check (source in ('Scripts', 'AFF Data')),
    product         text,
    category        text references categories (name),
    module          text,
    difficulty      text check (difficulty in ('Easy', 'Medium', 'Hard') or difficulty is null),
    question_text   text,
    answer_type     text check (answer_type in ('SCRIPT', 'KB', 'TICKET_RESOLUTION')),
    target_id       text,
    target_title    text,
    generation_source_record text
);

-- Unified RAG search layer. All three answer sources in one vector space.
-- Content built from:
--   SCRIPT:            script_purpose + script_text_sanitized
--   KB:                body
--   TICKET_RESOLUTION: description + root_cause + resolution
create table retrieval_corpus (
    source_type     text not null check (source_type in ('SCRIPT', 'KB', 'TICKET_RESOLUTION')),
    source_id       text not null,
    title           text,
    content         text,
    category        text references categories (name),
    module          text,
    tags            text default '',
    embedding       vector(1536),
    primary key (source_type, source_id)
);
