-- ============================================================================
-- Migration 005: Extend metadata filter to support "no topic_id" fallback
-- ============================================================================
-- Adds support for {"has_topic_id": false}: row must NOT have a non-empty
-- topic_id. Used by the fallback phase of two-phase retrieval when phase 1
-- (chunks with topic_id) returns zero results.
--
-- Backward-compatible with migration 004: the {"has_topic_id": true} and
-- {"topic_id": "..."} branches behave identically. Per-table match_* functions
-- do not need to change — they already call vector_match_apply_metadata_filter.
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
        WHEN filter ? 'has_topic_id' AND (filter ->> 'has_topic_id')::boolean = TRUE THEN
            doc_metadata ? 'topic_id'
            AND NULLIF(BTRIM(doc_metadata ->> 'topic_id'), '') IS NOT NULL
        WHEN filter ? 'has_topic_id' AND (filter ->> 'has_topic_id')::boolean = FALSE THEN
            NOT (doc_metadata ? 'topic_id')
            OR NULLIF(BTRIM(doc_metadata ->> 'topic_id'), '') IS NULL
        WHEN filter ? 'topic_id' THEN
            doc_metadata ->> 'topic_id' = filter ->> 'topic_id'
        ELSE TRUE
    END;
$$;

COMMENT ON FUNCTION public.vector_match_apply_metadata_filter(jsonb, jsonb) IS
    'RPC filter: {} = all; has_topic_id=true = curricular; has_topic_id=false = auxiliary; topic_id = exact match';
