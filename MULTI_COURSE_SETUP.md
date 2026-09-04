# Multi-Course Setup Guide

## 🎯 Overview

The chatbot now supports **multiple courses** with dynamic table switching. Each course has its own:
- Supabase vector table
- RPC search function
- Configuration stored in `course_configurations` table

---

## 📝 What Was Implemented

### 1. Database Schema (`migrations/002_course_configurations.sql`)
- **Table**: `course_configurations` - Maps course_id → table_name + rpc_function
- **Columns**: course_id, course_name, table_name, rpc_function, active, metadata
- **Functions**: Auto-update timestamps, helper views

### 2. Backend Infrastructure
- **`app/models.py`**: Pydantic models for validation
- **`app/course_config.py`**: Service layer with caching (5-min TTL)
- **Updated `app/main.py`**:
  - ✅ Course management API (CRUD endpoints)
  - ✅ Dynamic chat endpoint (accepts `course_id`)
  - ✅ Ingestion validation (verifies course exists)
- **Updated `worker.py`**:
  - ✅ Dynamic vector store creation per job
  - ✅ Course-specific indexing

### 3. Frontend
- **Updated `frontend/chat-widget.js`**:
  - ✅ Accepts `CHATBOT_COURSE_ID` (required)
  - ✅ Accepts `CHATBOT_USER_ID` (optional)
  - ✅ Sends `course_id` and `user_id` in requests
  - ✅ Validation errors if course_id missing

---

## 🚀 Setup Instructions

### Step 1: Run Database Migration

1. Open **Supabase SQL Editor**
2. Copy and paste `migrations/002_course_configurations.sql`
3. Execute the script
4. Verify:
   ```sql
   SELECT * FROM course_configurations;
   ```

### Step 2: Create Your First Course Configuration

**Option A: Via API (Recommended)**

```bash
curl -X POST http://localhost:8080/api/v1/courses \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "course_mant_mec",
    "course_name": "Mantenimiento Mecánico Automotriz",
    "course_slug": "mantenimiento-mecanico",
    "table_name": "course_mant_mec_vectors",
    "rpc_function": "match_course_mant_mec_vectors",
    "active": true,
    "description": "Curso de mantenimiento mecánico",
    "metadata": {"instructor": "John Doe", "level": "intermediate"}
  }'
```

**Option B: Via SQL (Direct)**

```sql
INSERT INTO course_configurations (
    course_id,
    course_name,
    course_slug,
    table_name,
    rpc_function,
    active,
    description
) VALUES (
    'course_mant_mec',
    'Mantenimiento Mecánico Automotriz',
    'mantenimiento-mecanico',
    'course_mant_mec_vectors',
    'match_course_mant_mec_vectors',
    true,
    'Curso de mantenimiento mecánico'
);
```

### Step 3: Create Supabase Table and RPC Function

For each course, you need to create:

1. **Vector table** (replace `course_mant_mec_vectors` with your table name):

```sql
CREATE TABLE course_mant_mec_vectors (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding halfvec(3072),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create HNSW index for fast vector search
CREATE INDEX idx_course_mant_mec_embedding_hnsw
    ON course_mant_mec_vectors
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

2. **RPC search function**:

```sql
CREATE OR REPLACE FUNCTION match_course_mant_mec_vectors(
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
    FROM course_mant_mec_vectors t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;
```

### Step 4: Restart Services

```bash
# Rebuild and restart
docker compose build
docker compose up -d

# Verify services are running
docker compose ps

# Check logs
docker compose logs -f fastapi_app
docker compose logs -f ingestion_worker
```

---

## 🧪 Testing the Implementation

### Test 1: List Courses

```bash
curl http://localhost:8080/api/v1/courses
```

**Expected response:**
```json
{
  "courses": [
    {
      "id": 1,
      "course_id": "course_mant_mec",
      "course_name": "Mantenimiento Mecánico Automotriz",
      "table_name": "course_mant_mec_vectors",
      "rpc_function": "match_course_mant_mec_vectors",
      "active": true,
      "created_at": "2025-01-15T10:00:00Z",
      ...
    }
  ],
  "total": 1
}
```

### Test 2: Get Specific Course

```bash
curl http://localhost:8080/api/v1/courses/course_mant_mec
```

### Test 3: Ingest Content

```bash
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "unique_content_id": "course_mant_mec_topic_001",
    "course_id": "course_mant_mec",
    "course_name": "Mantenimiento Mecánico Automotriz",
    "topic_id": "topic_001",
    "model": "standard",
    "version": "1.0",
    "title": "Introducción al Mantenimiento",
    "module": "Módulo 1",
    "notes": "Contenido inicial",
    "version_data": "2025-01-15",
    "content": "El mantenimiento mecánico automotriz es una disciplina fundamental que garantiza el funcionamiento óptimo de los vehículos. Incluye revisiones periódicas, cambios de aceite, inspección de frenos, y mantenimiento de sistemas de transmisión."
  }'
```

**Expected response:**
```json
{
  "message": "Content received and queued for processing.",
  "job_id": 1
}
```

**Monitor worker logs:**
```bash
docker compose logs -f ingestion_worker
```

Look for:
- ✅ Job dequeued
- ✅ Course config retrieved
- ✅ Old content deleted
- ✅ New content indexed
- ✅ Job completed

### Test 4: Query the Chat

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Qué es el mantenimiento mecánico?",
    "course_id": "course_mant_mec",
    "user_id": "test_user_123"
  }'
```

**Expected response:**
```json
{
  "answer": "El mantenimiento mecánico automotriz es...",
  "sources": ["Introducción al Mantenimiento"],
  "course_id": "course_mant_mec",
  "user_id": "test_user_123"
}
```

### Test 5: Frontend Widget

Create a test HTML file:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Test Multi-Course Widget</title>
</head>
<body>
  <h1>Testing Multi-Course Chat Widget</h1>

  <!-- Configure BEFORE loading widget -->
  <script>
    window.CHATBOT_COURSE_ID = 'course_mant_mec';  // Required
    window.CHATBOT_USER_ID = 'test_user_123';      // Optional
    window.CHATBOT_TITLE = 'Asistente de Mantenimiento';
    window.CHATBOT_SUBTITLE = 'Pregúntame sobre mantenimiento mecánico';
  </script>

  <!-- Load widget -->
  <script src="chat-widget.js"></script>
</body>
</html>
```

Open in browser and test:
1. Widget should appear
2. Ask: "¿Qué es el mantenimiento mecánico?"
3. Should receive formatted markdown answer with sources

---

## 🔄 Adding Additional Courses

### Quick Guide

1. **Create course config** (via API or SQL)
2. **Create Supabase table** (use template above)
3. **Create RPC function** (use template above)
4. **Ingest content** (via POST /api/v1/ingest)
5. **Test chat** (via POST /api/chat with new course_id)

### Example: Second Course

```bash
# 1. Create config
curl -X POST http://localhost:8080/api/v1/courses \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "course_elect_auto",
    "course_name": "Electrónica Automotriz",
    "course_slug": "electronica-automotriz",
    "table_name": "course_elect_auto_vectors",
    "rpc_function": "match_course_elect_auto_vectors",
    "active": true
  }'

# 2. Run SQL to create table + RPC (adapt templates above)
# 3. Ingest content with course_id="course_elect_auto"
# 4. Test chat with course_id="course_elect_auto"
```

---

## 📊 Course Management API Reference

### List All Courses
```http
GET /api/v1/courses?active_only=true
```

### Get Course Details
```http
GET /api/v1/courses/{course_id}
```

### Create Course
```http
POST /api/v1/courses
Content-Type: application/json

{
  "course_id": "string",
  "course_name": "string",
  "course_slug": "string",
  "table_name": "string",
  "rpc_function": "string",
  "active": true,
  "description": "string",
  "metadata": {}
}
```

### Update Course
```http
PUT /api/v1/courses/{course_id}
Content-Type: application/json

{
  "course_name": "Updated Name",
  "active": false
}
```

### Delete Course
```http
DELETE /api/v1/courses/{course_id}?hard_delete=false
```

---

## 🛠️ Troubleshooting

### Error: "Course not found or inactive"

**Cause:** The course_id doesn't exist in `course_configurations`

**Solution:**
```sql
-- Check if course exists
SELECT * FROM course_configurations WHERE course_id = 'your_course_id';

-- If missing, create it via API or SQL
```

### Error: "Table does not exist"

**Cause:** The Supabase table hasn't been created yet

**Solution:** Run the CREATE TABLE SQL for your course (see Step 3)

### Error: "Function does not exist"

**Cause:** The RPC function hasn't been created

**Solution:** Run the CREATE FUNCTION SQL for your course (see Step 3)

### Worker Fails to Process Jobs

**Check worker logs:**
```bash
docker compose logs -f ingestion_worker
```

Common issues:
- Course config not found → Create the course
- Table doesn't exist → Create the Supabase table
- RPC function missing → Create the RPC function

### Widget Shows Configuration Error

**Cause:** `CHATBOT_COURSE_ID` not set

**Solution:**
```html
<script>
  window.CHATBOT_COURSE_ID = 'your_course_id';
</script>
<script src="chat-widget.js"></script>
```

---

## ✅ Verification Checklist

- [ ] Migration SQL executed successfully
- [ ] At least one course created in `course_configurations`
- [ ] Supabase table created for the course
- [ ] RPC function created for the course
- [ ] HNSW index created on the table
- [ ] Services restarted (API + worker)
- [ ] Course API endpoints work (GET /api/v1/courses)
- [ ] Content ingestion works (POST /api/v1/ingest)
- [ ] Worker processes jobs successfully
- [ ] Chat endpoint works with course_id (POST /api/chat)
- [ ] Widget sends course_id in requests
- [ ] Multiple courses can coexist independently

---

## 🎉 Success Criteria

You've successfully set up multi-course support when:

1. ✅ You can create courses via API
2. ✅ You can ingest content for different courses
3. ✅ You can query different courses independently
4. ✅ Each course has its own vector table
5. ✅ The widget works with configurable course_id
6. ✅ Course data is isolated (Course A can't access Course B data)

---

## 📚 Next Steps

1. **Migrate existing data**: If you have an existing course, create a config for it
2. **Add more courses**: Use the templates to add additional courses
3. **Monitor performance**: Check logs and Supabase metrics
4. **Implement UI**: Create an admin panel to manage courses
5. **Add analytics**: Track course usage via user_id

---

*Last updated: 2025-01-15*
*Feature: Multi-Course Dynamic Table Switching*
