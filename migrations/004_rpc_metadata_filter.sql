-- ============================================================================
-- Migration 004: Metadata filter for vector match RPC functions
-- ============================================================================
-- Enables the ``filter`` jsonb parameter used by the chatbot for two-phase
-- retrieval (prefer chunks with topic_id).
--
-- After running this script, update EACH course match_* function to add:
--   AND vector_match_apply_metadata_filter(t.metadata, filter)
-- in the WHERE clause (see example at the bottom).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.vector_match_apply_metadata_filter(
    doc_metadata jsonb,
    filter jsonb
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN filter IS NULL OR filter = '{}'::jsonb THEN TRUE
        WHEN COALESCE((filter ->> 'has_topic_id')::boolean, FALSE) THEN
            doc_metadata ? 'topic_id'
            AND NULLIF(BTRIM(doc_metadata ->> 'topic_id'), '') IS NOT NULL
        WHEN filter ? 'topic_id' THEN
            doc_metadata ->> 'topic_id' = filter ->> 'topic_id'
        ELSE TRUE
    END;
$$;

COMMENT ON FUNCTION public.vector_match_apply_metadata_filter(jsonb, jsonb) IS
    'Evaluates RPC filter: {} = all rows; has_topic_id=true = curricular chunks; topic_id = exact match';

-- Optional: index to speed up has_topic_id scans (expression index on jsonb)
-- Run per vector table, e.g.:
-- CREATE INDEX IF NOT EXISTS idx_ec0241_metadata_topic_id_present
--   ON ec0241_gemi_mantenimiento_industrial ((metadata ? 'topic_id'))
--   WHERE metadata ? 'topic_id';

-- ----------------------------------------------------------------------------
-- EXAMPLE: patch an existing match function (replace table name and function)
-- ----------------------------------------------------------------------------
/*
CREATE OR REPLACE FUNCTION match_ec0241_gemi_mantenimiento_industrial(
    query_embedding halfvec(3072),
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (id bigint, content text, metadata jsonb, similarity double precision)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    PERFORM set_config('hnsw.ef_search', '20', true);
    RETURN QUERY
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM ec0241_gemi_mantenimiento_industrial t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
      AND public.vector_match_apply_metadata_filter(t.metadata, filter)
    ORDER BY t.embedding <=> query_embedding ASC
    LIMIT match_count;
END;
$$;
*/
