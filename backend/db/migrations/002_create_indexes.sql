-- 002: Create Indexes (b-tree, HNSW vector, GIN full-text)

-- Tickets
create index idx_tickets_status          on tickets (status);
create index idx_tickets_priority        on tickets (priority);
create index idx_tickets_tier            on tickets (tier);
create index idx_tickets_script_id       on tickets (script_id);
create index idx_tickets_kb_article_id   on tickets (kb_article_id);
create index idx_tickets_generated_kb    on tickets (generated_kb_article_id);

-- Conversations
create index idx_conversations_category  on conversations (category);
create index idx_conversations_channel   on conversations (channel);
create index idx_conversations_sentiment on conversations (sentiment);

-- KB articles
create index idx_kb_source_type          on knowledge_articles (source_type);
create index idx_kb_category             on knowledge_articles (category);
create index idx_kb_status               on knowledge_articles (status);

-- KB lineage
create index idx_kb_lineage_source       on kb_lineage (source_type, source_id);

-- Learning events
create index idx_learning_status         on learning_events (final_status);
create index idx_learning_ticket         on learning_events (trigger_ticket_number);
create index idx_learning_kb             on learning_events (proposed_kb_article_id);

-- Questions
create index idx_questions_answer_type   on questions (answer_type);
create index idx_questions_target_id     on questions (target_id);
create index idx_questions_category      on questions (category);
create index idx_questions_difficulty    on questions (difficulty);

-- Scripts
create index idx_scripts_category        on scripts_master (category);
create index idx_scripts_module          on scripts_master (module);

-- Script placeholders
create index idx_script_placeholders_placeholder on script_placeholders (placeholder);

-- Retrieval corpus: b-tree for pre-filtering
create index idx_corpus_source_type      on retrieval_corpus (source_type);
create index idx_corpus_category         on retrieval_corpus (category);

-- Retrieval corpus: HNSW for vector similarity search (cosine distance)
create index idx_corpus_embedding on retrieval_corpus
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

-- Full-text search (GIN) on retrieval corpus
create index idx_corpus_content_fts on retrieval_corpus
    using gin (to_tsvector('english', coalesce(content, '')));
create index idx_corpus_title_fts on retrieval_corpus
    using gin (to_tsvector('english', coalesce(title, '')));

-- Full-text search on source tables (for non-RAG queries)
create index idx_conversations_transcript_fts on conversations
    using gin (to_tsvector('english', coalesce(transcript, '')));
create index idx_tickets_description_fts on tickets
    using gin (to_tsvector('english', coalesce(description, '')));
create index idx_tickets_resolution_fts on tickets
    using gin (to_tsvector('english', coalesce(resolution, '')));