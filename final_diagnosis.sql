-- ============================================================================
-- Final Diagnosis: Test with Proper 3072-dimension Vector
-- ============================================================================
-- Everything looks healthy, so let's test if the index is actually being used
-- ============================================================================

-- ============================================================================
-- STEP 1: Test Query Performance with a Real Vector
-- ============================================================================

-- First, let's get a real embedding from the table to test with
-- This ensures we're using a properly formatted 3072-dimension vector

-- Get a sample embedding from the table
WITH sample_embedding AS (
    SELECT embedding
    FROM ec1530_gemi_mantenimiento_electromecanico
    LIMIT 1
)
SELECT
    id,
    content,
    (1 - (embedding <=> (SELECT embedding FROM sample_embedding))) AS similarity
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> (SELECT embedding FROM sample_embedding))) >= 0.5
ORDER BY similarity DESC
LIMIT 3;

-- If this returns quickly (< 1 second), the index is working!
-- If this times out, there's a deeper issue

-- ============================================================================
-- STEP 2: Test the RPC Function Directly
-- ============================================================================

-- Test the RPC function with a real embedding
DO $$
DECLARE
    test_embedding halfvec(3072);
BEGIN
    -- Get a sample embedding
    SELECT embedding INTO test_embedding
    FROM ec1530_gemi_mantenimiento_electromecanico
    LIMIT 1;

    -- Test the RPC function
    RAISE NOTICE 'Testing RPC function...';
    PERFORM * FROM match_ec1530_gemi_mantenimiento_electromecanico(
        query_embedding := test_embedding,
        match_count := 3,
        match_threshold := 0.5
    );
    RAISE NOTICE 'RPC function completed successfully';
END $$;

-- ============================================================================
-- STEP 3: Check if Query Planner is Using the Index
-- ============================================================================

-- We need to check if PostgreSQL is actually using the HNSW index
-- Let's enable query logging temporarily

-- Check current work_mem (if too low, index might not be used)
SHOW work_mem;

-- Check if effective_cache_size is reasonable
SHOW effective_cache_size;

-- ============================================================================
-- STEP 4: Test with Different Thresholds
-- ============================================================================

-- Maybe threshold 0.5 is too low and returns too many candidates
-- Test how many rows match different thresholds

WITH sample_embedding AS (
    SELECT embedding
    FROM ec1530_gemi_mantenimiento_electromecanico
    LIMIT 1
)
SELECT
    'Threshold 0.9' as threshold,
    COUNT(*) as matching_rows
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> (SELECT embedding FROM sample_embedding))) >= 0.9
UNION ALL
SELECT
    'Threshold 0.7',
    COUNT(*)
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> (SELECT embedding FROM sample_embedding))) >= 0.7
UNION ALL
SELECT
    'Threshold 0.5',
    COUNT(*)
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> (SELECT embedding FROM sample_embedding))) >= 0.5
UNION ALL
SELECT
    'Threshold 0.3',
    COUNT(*)
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> (SELECT embedding FROM sample_embedding))) >= 0.3;

-- If threshold 0.5 returns thousands of rows, that's the problem!

-- ============================================================================
-- STEP 5: Run ANALYZE (Force Statistics Update)
-- ============================================================================

-- Even though the index exists, PostgreSQL might need updated statistics
ANALYZE ec1530_gemi_mantenimiento_electromecanico;

-- ============================================================================
-- STEP 6: Increase HNSW Search Parameters (if needed)
-- ============================================================================

-- HNSW has a trade-off between speed and accuracy
-- The ef_search parameter controls this (default is usually 40)
-- If queries are slow, we might need to adjust this

-- Check current setting
SHOW hnsw.ef_search;

-- To increase (makes search more thorough but slower):
-- SET hnsw.ef_search = 100;

-- To decrease (makes search faster but less accurate):
-- SET hnsw.ef_search = 20;

-- ============================================================================
-- POTENTIAL FIX: Increase Statement Timeout
-- ============================================================================

-- The timeout might be too aggressive
-- Check current timeout
SHOW statement_timeout;

-- If it's very low (like 10s), temporarily increase it for testing
-- SET statement_timeout = '30s';

-- Then test the query again

-- ============================================================================
-- STEP 7: Check for Table Bloat
-- ============================================================================

-- Check if table needs vacuuming
SELECT
    schemaname,
    tablename,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows,
    CASE
        WHEN n_live_tup > 0
        THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
        ELSE 0
    END as dead_row_percentage,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico';

-- If dead_row_percentage > 20%, run:
-- VACUUM ANALYZE ec1530_gemi_mantenimiento_electromecanico;

-- ============================================================================
-- STEP 8: Check Supabase-Specific Settings
-- ============================================================================

-- Supabase might have specific timeout settings
-- Check if there's a connection pooler timeout

-- Also check PostgREST specific settings
SHOW pgrst.db_pool_timeout;
SHOW pgrst.db_max_rows;

-- ============================================================================
-- DIAGNOSTIC INTERPRETATION
-- ============================================================================

/*
Based on your results so far, everything looks healthy:
- Index: ✅ Valid and ready (169 MB for 30k rows is good)
- Data: ✅ All 30,769 rows have embeddings
- RPC: ✅ Function definition looks correct

MOST LIKELY CAUSES at this point:

1. **Threshold too low (0.5)**: If many vectors have similarity > 0.5,
   the query returns too many candidates and is slow. Try increasing to 0.7.

2. **Statement timeout too aggressive**: Supabase might have a 10-second
   timeout which is cutting off the query. The query might actually work
   but takes 11-12 seconds.

3. **HNSW ef_search parameter**: Might be set too high, making search slow.

4. **Cold cache**: First query after restart is always slower. Try running
   the same query twice.

5. **Network latency**: The 9-second timeout might include network overhead
   from the API to Supabase and back.

RECOMMENDED ACTIONS:

1. Run STEP 4 to check how many rows match threshold 0.5
2. If it's > 1000 rows, increase threshold to 0.7 in your .env:
   MATCH_THRESHOLD=0.7

3. Run ANALYZE to update statistics

4. Try the query again

5. If still slow, increase statement_timeout temporarily to isolate
   whether it's actually timing out or just hitting the limit
*/
