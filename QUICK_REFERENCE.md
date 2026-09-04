# Quick Reference Card

## ⚡ Validated Configuration (Production-Ready)

```bash
# Copy these exact values to your .env file
MATCH_THRESHOLD=0.5          # ⭐ CRITICAL - Validated with 30k+ vectors
SIMILARITY_TOP_K=5
CHUNK_SIZE=512
CHUNK_OVERLAP=20
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSIONS=3072
GEMINI_MODEL=models/gemini-2.5-flash
```

---

## 📋 New Course Setup (3-Step Process)

### 1. Create in Supabase (SQL Editor)
```sql
-- Table + Index (both required!)
CREATE TABLE course_xyz_vectors (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding halfvec(3072),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_course_xyz_vectors_hnsw
ON course_xyz_vectors
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Optimized RPC Function
CREATE OR REPLACE FUNCTION match_course_xyz_vectors(
    query_embedding halfvec(3072),
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE(id bigint, content text, metadata jsonb, similarity double precision)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    PERFORM set_config('hnsw.ef_search', '20', true);
    RETURN QUERY
    SELECT t.id, t.content, t.metadata,
           (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM course_xyz_vectors t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    ORDER BY (t.embedding <=> query_embedding) ASC
    LIMIT match_count;
END;
$$;

-- Update statistics
ANALYZE course_xyz_vectors;
```

### 2. Register Course (API)
```bash
curl -X POST http://localhost:8080/api/v1/courses \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "course_xyz",
    "course_name": "Course Name",
    "course_slug": "course-slug",
    "table_name": "course_xyz_vectors",
    "rpc_function": "match_course_xyz_vectors",
    "active": true
  }'
```

### 3. Ingest Content
```bash
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "unique_content_id": "course_xyz_topic_001",
    "course_id": "course_xyz",
    "content": "Your content here..."
  }'
```

---

## 🐛 Troubleshooting (Top 3 Issues)

### Issue 1: Timeout Error
```sql
-- Run this in Supabase SQL Editor
ANALYZE your_table_name;
```

### Issue 2: Empty Results
```bash
# In .env - Lower threshold
MATCH_THRESHOLD=0.5  # From 0.8

# Restart
docker compose restart fastapi_app
```

### Issue 3: Slow Queries
```sql
-- Check if HNSW index exists
SELECT indexname FROM pg_indexes
WHERE tablename = 'your_table'
  AND indexname LIKE '%hnsw%';

-- If missing, create it (see step 1 above)
```

---

## 🔍 Health Check Commands

```bash
# Check services
docker compose ps

# Check API logs
docker compose logs -f fastapi_app

# Check worker logs
docker compose logs -f ingestion_worker

# Test API
curl http://localhost:8080/health

# List courses
curl http://localhost:8080/api/v1/courses
```

---

## 📊 Key Metrics

| What | Command | Good | Bad |
|------|---------|------|-----|
| **Response time** | Check logs | < 3s | > 5s |
| **Index exists** | SQL query | ✅ Yes | ❌ No |
| **Last ANALYZE** | `pg_stat_user_tables` | < 1 day | > 1 week |
| **Avg content length** | `AVG(LENGTH(content))` | > 500 | < 100 |

---

## 📚 Full Documentation

- **`COURSE_SETUP_BEST_PRACTICES.md`** - Complete guide with troubleshooting
- **`MULTI_COURSE_SETUP.md`** - Multi-course architecture setup
- **`CLAUDE.md`** - Full architecture documentation

---

*Keep this card handy when setting up new courses!*
