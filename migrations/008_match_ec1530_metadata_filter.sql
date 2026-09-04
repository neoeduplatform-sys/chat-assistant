-- ============================================================================
-- Migration 008: Apply metadata filter to match_ec1530_gemi_mantenimiento_electromecanico
-- ============================================================================
-- Course table: ec1530_gemi_mantenimiento_electromecanico
-- RPC function: match_ec1530_gemi_mantenimiento_electromecanico
--
-- Prerequisites (run first if not already applied):
--   - migrations/004_rpc_metadata_filter.sql  (vector_match_apply_metadata_filter)
--   - migrations/005_rpc_filter_no_topic_id.sql  (has_topic_id: false branch)
--
-- Change summary:
--   BEFORE: ``filter`` parameter may exist in signature but was IGNORED in WHERE.
--           Two-phase retrieval (has_topic_id true/false) had no effect.
--   AFTER:  WHERE clause calls public.vector_match_apply_metadata_filter(t.metadata, filter)
--           so phase 1 returns curricular chunks and phase 2 can return legacy/auxiliary.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- VERSION BACKUP (pre-patch)
-- Do not run — documentation and rollback reference only.
-- ----------------------------------------------------------------------------
/*
CREATE OR REPLACE FUNCTION public.match_ec1530_gemi_mantenimiento_electromecanico(
    query_embedding halfvec,
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE(id bigint, content text, metadata jsonb, similarity double precision)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    -- Optimize HNSW search speed
    PERFORM set_config('hnsw.ef_search', '20', true);

    RETURN QUERY
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM ec1530_gemi_mantenimiento_electromecanico t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    -- NOTE: filter parameter was declared but NOT applied here
    ORDER BY (t.embedding <=> query_embedding) ASC  -- Order by distance (faster)
    LIMIT match_count;
END;
$$;
*/


-- ----------------------------------------------------------------------------
-- VERSION MODIFICADA (aplicar en Supabase)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_ec1530_gemi_mantenimiento_electromecanico(
    query_embedding halfvec,
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE(id bigint, content text, metadata jsonb, similarity double precision)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    PERFORM set_config('hnsw.ef_search', '20', true);

    RETURN QUERY
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM ec1530_gemi_mantenimiento_electromecanico t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
      AND public.vector_match_apply_metadata_filter(t.metadata, filter)
    ORDER BY (t.embedding <=> query_embedding) ASC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION public.match_ec1530_gemi_mantenimiento_electromecanico(
    halfvec, integer, double precision, jsonb
) IS
    'Vector similarity search for ec1530_gemi_mantenimiento_electromecanico with optional metadata filter (has_topic_id, topic_id).';


-- ----------------------------------------------------------------------------
-- Verification (optional)
-- ----------------------------------------------------------------------------
-- Confirm the filter line is present:
--
-- SELECT pg_get_functiondef(p.oid)
-- FROM pg_proc p
-- JOIN pg_namespace n ON n.oid = p.pronamespace
-- WHERE p.proname = 'match_ec1530_gemi_mantenimiento_electromecanico';
--
-- Expected: body contains
--   AND public.vector_match_apply_metadata_filter(t.metadata, filter)
