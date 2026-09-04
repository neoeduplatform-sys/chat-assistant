# Course Setup Best Practices & Troubleshooting

## 📋 Overview

This document contains best practices, validated configurations, and troubleshooting steps for setting up new courses in the multi-course chatbot system.

**Last Updated:** 2025-01-15
**Validated Configuration:** Production-tested with 30,769 vectors

---

## ✅ Validated Configuration

### Working Setup (Tested & Confirmed)

```bash
# Embedding Configuration
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSIONS=3072

# RAG Configuration
SIMILARITY_TOP_K=5
MATCH_THRESHOLD=0.5          # ⭐ RECOMMENDED - Balanced precision/recall
CHUNK_SIZE=512
CHUNK_OVERLAP=20

# Model Configuration
GEMINI_MODEL=models/gemini-2.5-flash
```

### Why MATCH_THRESHOLD=0.5?

**Tested with 30,769 vectors:**
- ✅ **Threshold 0.5:** Returns 3-5 relevant results, good balance
- ⚠️ **Threshold 0.8:** Too strict, often returns 0 results
- ⚠️ **Threshold 0.3:** Too permissive, may return less relevant content

**Recommendation:** Start with `0.5`, adjust based on your content quality and user feedback.

---

## 🚀 Complete Course Setup Checklist

Use this checklist when adding a new course to ensure everything works correctly.

### Step 1: Create Course Configuration

```bash
curl -X POST http://localhost:8080/api/v1/courses \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "course_xyz",
    "course_name": "Course Full Name",
    "course_slug": "course-slug",
    "table_name": "course_xyz_vectors",
    "rpc_function": "match_course_xyz_vectors",
    "active": true,
    "description": "Course description"
  }'
```

**Verify:**
```bash
curl http://localhost:8080/api/v1/courses/course_xyz
```

---

### Step 2: Create Supabase Table

```sql
-- Create vector table
CREATE TABLE course_xyz_vectors (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding halfvec(3072),  -- Must match EMBEDDING_DIMENSIONS
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ⚠️ CRITICAL: Create HNSW index immediately (prevents timeouts!)
CREATE INDEX idx_course_xyz_vectors_embedding_hnsw
ON course_xyz_vectors
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Recommended: Add indexes on metadata for filtering
CREATE INDEX idx_course_xyz_vectors_metadata ON course_xyz_vectors USING gin(metadata);
```

**Verify index was created:**
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'course_xyz_vectors'
  AND indexname LIKE '%hnsw%';
```

Expected: Should show the HNSW index.

---

### Step 3: Create RPC Function (Optimized)

```sql
-- Create optimized RPC function for vector search
CREATE OR REPLACE FUNCTION match_course_xyz_vectors(
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
    -- Optimize HNSW search speed (lower = faster, less accurate)
    PERFORM set_config('hnsw.ef_search', '20', true);

    RETURN QUERY
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM course_xyz_vectors t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    ORDER BY (t.embedding <=> query_embedding) ASC
    LIMIT match_count;
END;
$$;
```

**Key optimizations:**
- ✅ Uses `plpgsql` (faster than `sql`)
- ✅ Sets `hnsw.ef_search=20` for speed
- ✅ Orders by distance (slightly faster than similarity)

**Verify function exists:**
```sql
SELECT proname, prosrc
FROM pg_proc
WHERE proname = 'match_course_xyz_vectors';
```

---

### Step 4: Update Table Statistics (CRITICAL!)

```sql
-- Update statistics so PostgreSQL knows how to use the index
ANALYZE course_xyz_vectors;
```

**Why this matters:** Without ANALYZE, PostgreSQL might not use your index properly, causing slow queries.

**Run ANALYZE:**
- ✅ After creating the table
- ✅ After ingesting content
- ✅ After any major data changes

---

### Step 5: Ingest Content

```bash
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "unique_content_id": "course_xyz_topic_001",
    "course_id": "course_xyz",
    "course_name": "Course Full Name",
    "topic_id": "topic_001",
    "model": "standard",
    "version": "1.0",
    "title": "Topic Title",
    "module": "Module 1",
    "notes": "Notes",
    "version_data": "2025-01-15",
    "content": "Your content here..."
  }'
```

**Monitor ingestion:**
```bash
docker compose logs -f ingestion_worker
```

Expected logs:
- ✅ Job dequeued
- ✅ Course config retrieved
- ✅ Old content deleted
- ✅ New content indexed
- ✅ Job completed

---

### Step 6: Run ANALYZE Again (After Ingestion)

```sql
-- Update statistics after ingesting data
ANALYZE course_xyz_vectors;
```

---

### Step 7: Test the Setup

#### A. Test RPC Function Directly

```sql
-- Test with a real embedding from the table
DO $$
DECLARE
    test_embedding halfvec(3072);
    result_count int;
BEGIN
    -- Get a sample embedding
    SELECT embedding INTO test_embedding
    FROM course_xyz_vectors
    LIMIT 1;

    -- Test the function
    SELECT COUNT(*) INTO result_count
    FROM match_course_xyz_vectors(
        query_embedding := test_embedding,
        match_count := 5,
        match_threshold := 0.5
    );

    RAISE NOTICE 'Results found: %', result_count;
END $$;
```

**Expected:** Should return > 0 results

#### B. Test via API

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Test question about your course content",
    "course_id": "course_xyz"
  }'
```

**Expected response:**
- ✅ `answer`: Contains relevant response
- ✅ `sources`: Array with 3-5 source documents
- ✅ Response time: < 3 seconds

---

## 🐛 Common Issues & Solutions

### Issue 1: "Statement Timeout" Error

**Symptom:**
```
"message":"canceling statement due to statement timeout"
```

**Causes & Solutions:**

#### A. Missing HNSW Index
```sql
-- Check if index exists
SELECT indexname FROM pg_indexes
WHERE tablename = 'your_table'
  AND indexname LIKE '%hnsw%';

-- If missing, create it
CREATE INDEX idx_your_table_embedding_hnsw
ON your_table
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

#### B. Stale Statistics
```sql
-- Update statistics
ANALYZE your_table;
```

#### C. Threshold Too Low
If threshold is < 0.5, too many rows match and query is slow.

**Fix:** Increase threshold to 0.5 or higher in `.env`

---

### Issue 2: "Empty Knowledge Base" / No Results

**Symptom:**
```json
{"answer": "Empty Response", "sources": null}
```

**Causes & Solutions:**

#### A. Threshold Too High
```bash
# In .env - Lower the threshold
MATCH_THRESHOLD=0.5  # From 0.8
```

**Test different thresholds:**
```sql
WITH test_embedding AS (
    SELECT embedding FROM your_table LIMIT 1
)
SELECT
    '0.3' as threshold, COUNT(*) as results
FROM match_your_function((SELECT embedding FROM test_embedding), 5, 0.3)
UNION ALL SELECT '0.5', COUNT(*)
FROM match_your_function((SELECT embedding FROM test_embedding), 5, 0.5)
UNION ALL SELECT '0.7', COUNT(*)
FROM match_your_function((SELECT embedding FROM test_embedding), 5, 0.7);
```

#### B. No Content Ingested
```sql
-- Check if table has data
SELECT COUNT(*) as total_rows,
       COUNT(embedding) as rows_with_embedding
FROM your_table;
```

If 0 rows, ingest content first.

#### C. Content Too Short
```sql
-- Check content quality
SELECT
    AVG(LENGTH(content)) as avg_length,
    MIN(LENGTH(content)) as min_length,
    COUNT(CASE WHEN LENGTH(content) < 50 THEN 1 END) as short_chunks
FROM your_table;
```

If avg_length < 100, your chunking settings might be wrong.

---

### Issue 3: Slow Queries (> 5 seconds)

**Causes & Solutions:**

#### A. Run ANALYZE
```sql
ANALYZE your_table;
```

#### B. Check if Index is Being Used
```sql
EXPLAIN ANALYZE
SELECT id, content, (1 - (embedding <=> (SELECT embedding FROM your_table LIMIT 1))) AS sim
FROM your_table
WHERE (1 - (embedding <=> (SELECT embedding FROM your_table LIMIT 1))) >= 0.5
ORDER BY sim DESC
LIMIT 5;
```

**Look for:** "Index Scan using idx_..._hnsw" ✅
**Bad:** "Seq Scan on your_table" ❌

#### C. Optimize RPC Function
Use the optimized `plpgsql` version with `hnsw.ef_search=20` (see Step 3 above)

---

## 📊 Performance Benchmarks

### Expected Performance

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| **Vector search time** | < 1s | < 3s | > 5s |
| **Total response time** | < 3s | < 5s | > 10s |
| **Rows in table** | < 100k | < 500k | > 1M |
| **Index size** | ~5x rows | ~10x rows | > 20x rows |

### Test Query Performance

```sql
-- Time a typical query
\timing on

WITH test_embedding AS (
    SELECT embedding FROM your_table LIMIT 1
)
SELECT COUNT(*)
FROM match_your_function(
    (SELECT embedding FROM test_embedding),
    5,
    0.5
);
```

**Target:** < 500ms

---

## 🎯 Recommended Settings Summary

### For Small Tables (< 10k vectors)
```bash
MATCH_THRESHOLD=0.5
SIMILARITY_TOP_K=5
CHUNK_SIZE=512
CHUNK_OVERLAP=20
```

```sql
-- HNSW Index
WITH (m = 16, ef_construction = 64)

-- RPC Function
hnsw.ef_search = 20
```

### For Medium Tables (10k - 100k vectors)
```bash
MATCH_THRESHOLD=0.5
SIMILARITY_TOP_K=5
CHUNK_SIZE=512
CHUNK_OVERLAP=20
```

```sql
-- HNSW Index
WITH (m = 16, ef_construction = 64)

-- RPC Function
hnsw.ef_search = 20
```

### For Large Tables (> 100k vectors)
```bash
MATCH_THRESHOLD=0.6  # Slightly higher for better precision
SIMILARITY_TOP_K=3   # Fewer results
CHUNK_SIZE=512
CHUNK_OVERLAP=20
```

```sql
-- HNSW Index (lower parameters for speed)
WITH (m = 8, ef_construction = 32)

-- RPC Function
hnsw.ef_search = 10
```

---

## 🔍 Diagnostic Queries

### Quick Health Check

```sql
-- Comprehensive course health check
SELECT
    'Table Info' as metric,
    json_build_object(
        'total_rows', (SELECT COUNT(*) FROM your_table),
        'rows_with_embedding', (SELECT COUNT(embedding) FROM your_table),
        'avg_content_length', (SELECT AVG(LENGTH(content))::int FROM your_table),
        'table_size', pg_size_pretty(pg_relation_size('your_table'))
    ) as value
UNION ALL
SELECT
    'Index Info',
    json_build_object(
        'index_exists', EXISTS(
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'your_table'
            AND indexname LIKE '%hnsw%'
        ),
        'index_size', pg_size_pretty(pg_relation_size('idx_your_table_embedding_hnsw')),
        'last_analyze', (
            SELECT last_analyze
            FROM pg_stat_user_tables
            WHERE tablename = 'your_table'
        )
    ) as value;
```

---

## 📚 Related Documentation

- **Setup Guide:** `MULTI_COURSE_SETUP.md`
- **Architecture:** `CLAUDE.md`
- **Troubleshooting:** `fix_rpc_timeout.sql`
- **Diagnostics:** `deep_diagnostics.sql`

---

## ✅ Validation Checklist

Before going to production with a new course:

- [ ] Course configuration created (`course_configurations` table)
- [ ] Supabase table created with proper schema
- [ ] HNSW index created on `embedding` column
- [ ] RPC function created (optimized `plpgsql` version)
- [ ] ANALYZE run on table
- [ ] Content ingested successfully (check worker logs)
- [ ] ANALYZE run again after ingestion
- [ ] Test query returns results in < 3 seconds
- [ ] API endpoint returns answers with sources
- [ ] `MATCH_THRESHOLD=0.5` configured in `.env`
- [ ] Services restarted after configuration changes

---

## 🎓 Lessons Learned

### From Production Testing (Course: ec1530)

**Setup:** 30,769 vectors, 169 MB index, average content length 685 chars

**Key Findings:**

1. ✅ **HNSW index is MANDATORY** - Without it, queries timeout
2. ✅ **ANALYZE is CRITICAL** - Run after table creation AND after ingestion
3. ✅ **Threshold 0.5 is optimal** - Balances precision and recall
4. ✅ **Threshold 0.8 too strict** - Often returns 0 results
5. ✅ **plpgsql faster than sql** - For RPC functions
6. ✅ **ef_search=20 works well** - Good speed/accuracy tradeoff
7. ⚠️ **Short content problematic** - Minimum 50 chars recommended
8. ⚠️ **API timeouts separate from DB** - PostgREST has 10s timeout

**Recommended Workflow:**
1. Create table + index (HNSW)
2. Run ANALYZE
3. Create RPC function (optimized)
4. Ingest content
5. Run ANALYZE again
6. Test thoroughly before production

---

*This document is based on real production experience and should be updated as new patterns emerge.*
