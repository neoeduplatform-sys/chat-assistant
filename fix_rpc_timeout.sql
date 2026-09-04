-- ============================================================================
-- Fix RPC Timeout Issue
-- ============================================================================
-- Problem: RPC timing out at ~9 seconds even with threshold 0.8 (178 matches)
-- Root Cause: Query is still slow + Supabase has aggressive timeouts
-- ============================================================================

-- ============================================================================
-- STEP 1: Test the RPC Function Directly (to isolate the issue)
-- ============================================================================

-- Test if the RPC function itself is slow
-- Run this in Supabase SQL Editor with timing enabled
\timing on

-- Get a sample embedding
DO $$
DECLARE
    start_time timestamp;
    end_time timestamp;
    duration interval;
    test_embedding halfvec(3072);
    result_count int;
BEGIN
    -- Get a sample embedding
    SELECT embedding INTO test_embedding
    FROM ec1530_gemi_mantenimiento_electromecanico
    LIMIT 1;

    -- Record start time
    start_time := clock_timestamp();

    -- Execute the RPC function
    SELECT COUNT(*) INTO result_count
    FROM match_ec1530_gemi_mantenimiento_electromecanico(
        query_embedding := test_embedding,
        match_count := 5,
        match_threshold := 0.8
    );

    -- Record end time
    end_time := clock_timestamp();
    duration := end_time - start_time;

    RAISE NOTICE 'Execution time: % ms', EXTRACT(milliseconds FROM duration);
    RAISE NOTICE 'Results returned: %', result_count;
END $$;

-- ============================================================================
-- STEP 2: Force PostgreSQL to Update Statistics
-- ============================================================================

-- This is critical! Even though data exists, stats might be stale
ANALYZE ec1530_gemi_mantenimiento_electromecanico;

-- Also run VACUUM to clean up any dead rows
VACUUM ANALYZE ec1530_gemi_mantenimiento_electromecanico;

-- ============================================================================
-- STEP 3: Check Query Plan (see if index is being used)
-- ============================================================================

-- Create a test query to see the execution plan
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    t.id,
    t.content,
    t.metadata,
    (1 - (t.embedding <=> (SELECT embedding FROM ec1530_gemi_mantenimiento_electromecanico LIMIT 1))) AS similarity
FROM ec1530_gemi_mantenimiento_electromecanico t
WHERE (1 - (t.embedding <=> (SELECT embedding FROM ec1530_gemi_mantenimiento_electromecanico LIMIT 1))) >= 0.8
ORDER BY similarity DESC
LIMIT 5;

-- LOOK FOR in the output:
-- ✅ "Index Scan using idx_ec1530_embedding_hnsw" - GOOD!
-- ❌ "Seq Scan on ec1530_gemi_mantenimiento_electromecanico" - BAD!

-- ============================================================================
-- STEP 4: Optimize RPC Function (if needed)
-- ============================================================================

-- The current RPC function is LANGUAGE sql which might be slower
-- Let's recreate it as plpgsql which is usually faster

DROP FUNCTION IF EXISTS match_ec1530_gemi_mantenimiento_electromecanico(halfvec, integer, double precision, jsonb);

CREATE OR REPLACE FUNCTION match_ec1530_gemi_mantenimiento_electromecanico(
    query_embedding halfvec(3072),
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE(
    id bigint,
    content text,
    metadata jsonb,
    similarity double precision
)
LANGUAGE plpgsql
STABLE
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
    ORDER BY (t.embedding <=> query_embedding) ASC  -- Order by distance (faster)
    LIMIT match_count;
END;
$$;

-- Note: Changed ORDER BY to use distance (<=>) which is slightly faster than similarity

-- ============================================================================
-- STEP 5: Set Function-Level Timeout (if needed)
-- ============================================================================

-- If the query legitimately takes 10+ seconds, we can increase timeout
-- just for this function

-- First, check current settings
SELECT
    proname,
    prosrc,
    proconfig
FROM pg_proc
WHERE proname = 'match_ec1530_gemi_mantenimiento_electromecanico';

-- Set a higher timeout for this specific function
ALTER FUNCTION match_ec1530_gemi_mantenimiento_electromecanico(halfvec, integer, double precision, jsonb)
SET statement_timeout = '60s';

-- ============================================================================
-- STEP 6: Increase HNSW ef_search Parameter (if too slow)
-- ============================================================================

-- HNSW has a runtime parameter that controls search quality vs speed
-- Lower ef_search = faster but less accurate
-- Higher ef_search = slower but more accurate

-- Check current setting (default is usually 40)
SHOW hnsw.ef_search;

-- Try lowering it for faster searches (trade-off: slightly less accurate)
ALTER DATABASE postgres SET hnsw.ef_search = 20;

-- Note: You might need Supabase admin access for this
-- Alternative: Set it per session in your RPC function:

DROP FUNCTION IF EXISTS match_ec1530_gemi_mantenimiento_electromecanico(halfvec, integer, double precision, jsonb);

CREATE OR REPLACE FUNCTION match_ec1530_gemi_mantenimiento_electromecanico(
    query_embedding halfvec(3072),
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE(
    id bigint,
    content text,
    metadata jsonb,
    similarity double precision
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    -- Set faster HNSW search for this function
    PERFORM set_config('hnsw.ef_search', '20', true);

    RETURN QUERY
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM ec1530_gemi_mantenimiento_electromecanico t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    ORDER BY (t.embedding <=> query_embedding) ASC
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- STEP 7: Alternative - Recreate Index with Different Parameters
-- ============================================================================

-- Current index has m=16, ef_construction=64
-- We can try with lower parameters for faster (but slightly less accurate) search

-- Drop existing index
DROP INDEX IF EXISTS idx_ec1530_embedding_hnsw;

-- Create new index with lower parameters (faster queries, slightly less recall)
CREATE INDEX idx_ec1530_embedding_hnsw
ON ec1530_gemi_mantenimiento_electromecanico
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 8, ef_construction = 32);  -- Lower parameters = faster queries

-- Note: This will take a few minutes to rebuild for 30k rows
-- Wait for completion before testing

-- Update statistics after recreating index
ANALYZE ec1530_gemi_mantenimiento_electromecanico;

-- ============================================================================
-- RECOMMENDED ACTION PLAN
-- ============================================================================

/*
Based on your situation, here's what I recommend in order:

1. **FIRST: Run ANALYZE** (STEP 2)
   - This updates PostgreSQL statistics
   - Should make query planner use the index properly
   - Takes < 1 second

2. **Test directly in SQL Editor** (STEP 1)
   - See if the query is actually fast when run directly
   - If fast (< 1 sec), the issue is API timeout
   - If slow (> 5 sec), need to optimize further

3. **If still slow: Recreate RPC as plpgsql** (STEP 4)
   - Change from LANGUAGE sql to LANGUAGE plpgsql
   - Add ef_search optimization
   - Should be noticeably faster

4. **If STILL slow: Lower HNSW parameters** (STEP 7)
   - Recreate index with m=8, ef_construction=32
   - This makes queries faster at cost of slight accuracy loss
   - For 30k rows, this should work great

5. **Last resort: Increase timeouts** (STEP 5)
   - Set function-level statement_timeout to 60s
   - But fix the performance issue instead if possible

EXPECTED RESULT:
After ANALYZE + plpgsql RPC function, query should complete in < 2 seconds
even with threshold 0.8
*/
