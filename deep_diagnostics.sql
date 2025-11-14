-- ============================================================================
-- Deep Diagnostics: Why is the query timing out despite having HNSW index?
-- ============================================================================
-- Run these queries in Supabase SQL Editor to identify the root cause
-- ============================================================================

-- ============================================================================
-- STEP 1: Check Index Health
-- ============================================================================

-- Check if index is valid (not corrupt)
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef,
    -- Check if index is valid
    NOT indisvalid as is_invalid,
    -- Check if index is ready
    indisready as is_ready
FROM pg_indexes
JOIN pg_class ON pg_indexes.indexname = pg_class.relname
JOIN pg_index ON pg_class.oid = pg_index.indexrelid
WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico'
    AND indexname = 'idx_ec1530_embedding_hnsw';

-- Check index size (should be significant if table has data)
SELECT
    pg_size_pretty(pg_relation_size('idx_ec1530_embedding_hnsw')) as index_size,
    pg_size_pretty(pg_relation_size('ec1530_gemi_mantenimiento_electromecanico')) as table_size;

-- ============================================================================
-- STEP 2: Check Table Data
-- ============================================================================

-- Count total rows
SELECT COUNT(*) as total_rows
FROM ec1530_gemi_mantenimiento_electromecanico;

-- Check if embeddings are NULL (big problem!)
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding) as rows_with_embedding,
    COUNT(*) - COUNT(embedding) as rows_with_null_embedding
FROM ec1530_gemi_mantenimiento_electromecanico;

-- Sample some data to verify structure
SELECT
    id,
    LENGTH(content) as content_length,
    jsonb_object_keys(metadata) as metadata_keys,
    CASE
        WHEN embedding IS NULL THEN 'NULL'
        ELSE 'HAS_EMBEDDING'
    END as embedding_status
FROM ec1530_gemi_mantenimiento_electromecanico
LIMIT 5;

-- ============================================================================
-- STEP 3: Analyze RPC Function Definition
-- ============================================================================

-- Get the full RPC function definition
SELECT pg_get_functiondef(oid)
FROM pg_proc
WHERE proname = 'match_ec1530_gemi_mantenimiento_electromecanico';

-- ============================================================================
-- STEP 4: Test Query Performance with EXPLAIN ANALYZE
-- ============================================================================

-- IMPORTANT: This will help us see if the index is being used
-- We need a real embedding to test, so let's create a dummy one

-- Test the RPC function with EXPLAIN (requires function modification)
-- First, let's test a direct query to see if index is used:

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    id,
    content,
    metadata,
    (1 - (embedding <=> '[0.1, 0.2, 0.3]'::halfvec(3072))) AS similarity
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> '[0.1, 0.2, 0.3]'::halfvec(3072))) >= 0.5
ORDER BY similarity DESC
LIMIT 3;

-- Look for "Index Scan using idx_ec1530_embedding_hnsw" in the output
-- If you see "Seq Scan" instead, the index is NOT being used!

-- ============================================================================
-- STEP 5: Check Table Statistics
-- ============================================================================

-- Check when table was last analyzed
SELECT
    schemaname,
    tablename,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows
FROM pg_stat_user_tables
WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico';

-- ============================================================================
-- POTENTIAL FIXES
-- ============================================================================

-- FIX 1: If statistics are stale (last_analyze is old or NULL)
-- Run ANALYZE to update table statistics
ANALYZE ec1530_gemi_mantenimiento_electromecanico;

-- FIX 2: If index is invalid
-- Rebuild the index
-- REINDEX INDEX idx_ec1530_embedding_hnsw;

-- FIX 3: If index is missing or corrupt
-- Drop and recreate
-- DROP INDEX IF EXISTS idx_ec1530_embedding_hnsw;
-- CREATE INDEX idx_ec1530_embedding_hnsw
-- ON ec1530_gemi_mantenimiento_electromecanico
-- USING hnsw (embedding halfvec_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- FIX 4: If embeddings are NULL
-- This means ingestion failed - check worker logs
-- Reingest the content

-- FIX 5: If table has too much data (millions of rows)
-- Increase ef_search parameter or adjust match_threshold
-- Or increase statement timeout (not recommended):
-- SET statement_timeout = '30s';

-- ============================================================================
-- STEP 6: Test with Increased Verbosity
-- ============================================================================

-- Enable query timing
\timing on

-- Test a simple count (should be fast)
SELECT COUNT(*) FROM ec1530_gemi_mantenimiento_electromecanico;

-- Test embedding existence (should be fast)
SELECT COUNT(*) FROM ec1530_gemi_mantenimiento_electromecanico WHERE embedding IS NOT NULL;

-- Test vector operation WITHOUT RPC (to isolate the issue)
-- This tests if the raw query is slow or if it's the RPC overhead
SELECT COUNT(*)
FROM ec1530_gemi_mantenimiento_electromecanico
WHERE (1 - (embedding <=> '[0.1, 0.2, 0.3]'::halfvec(3072))) >= 0.5;

-- ============================================================================
-- DIAGNOSTIC SUMMARY QUERIES
-- ============================================================================

-- Run this comprehensive diagnostic
SELECT
    'Table Info' as check_type,
    json_build_object(
        'total_rows', (SELECT COUNT(*) FROM ec1530_gemi_mantenimiento_electromecanico),
        'rows_with_embedding', (SELECT COUNT(embedding) FROM ec1530_gemi_mantenimiento_electromecanico),
        'table_size', pg_size_pretty(pg_relation_size('ec1530_gemi_mantenimiento_electromecanico')),
        'last_analyze', (SELECT last_analyze FROM pg_stat_user_tables WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico')
    ) as details
UNION ALL
SELECT
    'Index Info' as check_type,
    json_build_object(
        'index_exists', EXISTS(SELECT 1 FROM pg_indexes WHERE tablename = 'ec1530_gemi_mantenimiento_electromecanico' AND indexname = 'idx_ec1530_embedding_hnsw'),
        'index_size', pg_size_pretty(pg_relation_size('idx_ec1530_embedding_hnsw')),
        'index_valid', (SELECT indisvalid FROM pg_index JOIN pg_class ON pg_index.indexrelid = pg_class.oid WHERE pg_class.relname = 'idx_ec1530_embedding_hnsw')
    ) as details;

-- ============================================================================
-- EXPECTED RESULTS INTERPRETATION
-- ============================================================================

/*
WHAT TO LOOK FOR:

1. Index Health:
   - is_invalid = false (good)
   - is_ready = true (good)
   - If false, REINDEX is needed

2. Table Data:
   - total_rows > 0 (has data)
   - rows_with_null_embedding = 0 (all rows have embeddings)
   - If many NULLs, ingestion is broken

3. Statistics:
   - last_analyze should be recent (within hours/days)
   - If NULL or very old, run ANALYZE

4. EXPLAIN output:
   - Should show "Index Scan using idx_ec1530_embedding_hnsw"
   - Should NOT show "Seq Scan"
   - Execution time should be < 100ms

5. Table Size:
   - If > 1 million rows, might need parameter tuning
   - If table_size is 0 KB, no data was ingested

COMMON ISSUES:
- embeddings are NULL → Ingestion failed
- Index not being used → Need ANALYZE or query issue
- Index invalid → Need REINDEX
- No data → Need to run ingestion first
*/
