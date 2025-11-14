-- ============================================================================
-- Diagnostic and Fix Script for Statement Timeout Issue
-- ============================================================================
-- Problem: RPC function timing out with "canceling statement due to statement timeout"
-- Cause: Missing HNSW index on the embedding column
-- Table: ec1530_gemi_mantenimiento_electromecanico
--
-- Run these queries in Supabase SQL Editor
-- ============================================================================

-- ============================================================================
-- STEP 1: DIAGNOSTIC QUERIES
-- ============================================================================

-- Check if table exists
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_name = 'ec1530_gemi_mantenimiento_electromecanico'
) as table_exists;

-- Check table structure
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'ec1530_gemi_mantenimiento_electromecanico'
ORDER BY ordinal_position;

-- Check if there's data in the table
SELECT COUNT(*) as total_rows
FROM ec1530_gemi_mantenimiento_electromecanico;

-- Check for existing indexes on the table
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico';

-- Check if RPC function exists
SELECT
    p.proname as function_name,
    pg_get_functiondef(p.oid) as function_definition
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE p.proname = 'match_ec1530_gemi_mantenimiento_electromecanico'
    AND n.nspname = 'public';

-- ============================================================================
-- STEP 2: THE FIX - Create HNSW Index
-- ============================================================================
-- This is the most likely fix needed
-- HNSW index enables fast approximate nearest neighbor search
-- Without it, vector search does a slow sequential scan

-- Drop existing index if it exists (in case it's corrupted)
-- DROP INDEX IF EXISTS idx_ec1530_gemi_mantenimiento_electromecanico_embedding_hnsw;

-- Create HNSW index on the embedding column
CREATE INDEX IF NOT EXISTS idx_ec1530_gemi_mantenimiento_electromecanico_embedding_hnsw
ON ec1530_gemi_mantenimiento_electromecanico
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Verify the index was created
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico'
    AND indexname LIKE '%hnsw%';

-- ============================================================================
-- STEP 3: VERIFY THE FIX
-- ============================================================================

-- Test the RPC function with a dummy query
-- This should now return quickly (< 1 second)
SELECT * FROM match_ec1530_gemi_mantenimiento_electromecanico(
    query_embedding := ARRAY[0.1, 0.2]::halfvec(3072),  -- Dummy embedding
    match_count := 3,
    match_threshold := 0.5
);

-- ============================================================================
-- OPTIONAL: If RPC function is missing, create it
-- ============================================================================
-- Only run this if STEP 1 showed the function doesn't exist

/*
CREATE OR REPLACE FUNCTION match_ec1530_gemi_mantenimiento_electromecanico(
    query_embedding halfvec(3072),
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM ec1530_gemi_mantenimiento_electromecanico t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;
*/

-- ============================================================================
-- OPTIONAL: If table is missing, create it
-- ============================================================================
-- Only run this if STEP 1 showed the table doesn't exist

/*
CREATE TABLE IF NOT EXISTS ec1530_gemi_mantenimiento_electromecanico (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding halfvec(3072),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Then create the HNSW index (from STEP 2 above)
*/

-- ============================================================================
-- SUMMARY OF MOST LIKELY FIXES
-- ============================================================================

/*
MOST COMMON ISSUE: Missing HNSW index
Solution: Run the CREATE INDEX command from STEP 2

After creating the index:
1. Wait 10-30 seconds for index to build
2. Retry your chat query
3. Should now respond in < 1 second

If still slow after index:
- Check table has data: SELECT COUNT(*) FROM ec1530_gemi_mantenimiento_electromecanico;
- Check RPC function exists and is correct
- Check embedding column is halfvec(3072)
- Verify index was created: \di in psql or check pg_indexes
*/
