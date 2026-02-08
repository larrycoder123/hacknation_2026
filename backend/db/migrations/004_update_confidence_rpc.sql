-- 004: Postgres RPC for atomic confidence updates on retrieval_corpus.
-- Uses FOR UPDATE row locking to prevent read-then-write races.

create or replace function update_corpus_confidence(
    p_source_type   text,
    p_source_id     text,
    p_delta         float,
    p_increment_usage boolean default false
)
returns table (
    new_confidence  float,
    new_usage_count int
)
language plpgsql
as $$
declare
    v_confidence float;
    v_usage      int;
begin
    select rc.confidence, rc.usage_count
      into v_confidence, v_usage
      from retrieval_corpus rc
     where rc.source_type = p_source_type
       and rc.source_id   = p_source_id
       for update;

    if not found then
        raise exception 'retrieval_corpus row not found: (%, %)', p_source_type, p_source_id;
    end if;

    v_confidence := greatest(0.0, least(1.0, v_confidence + p_delta));
    if p_increment_usage then
        v_usage := v_usage + 1;
    end if;

    update retrieval_corpus rc
       set confidence  = v_confidence,
           usage_count = v_usage,
           updated_at  = now()
     where rc.source_type = p_source_type
       and rc.source_id   = p_source_id;

    new_confidence  := v_confidence;
    new_usage_count := v_usage;
    return next;
end;
$$;
