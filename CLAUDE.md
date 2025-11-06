# Chatbot Educativo - Documentación de Arquitectura

## 📋 Notas Importantes
- Docker CLI es `docker` en lugar de `docker-compose` en este sistema

---

## 🏗️ Arquitectura General

### Stack Tecnológico

```
┌─────────────────────────────────────────────────────────────┐
│                    CHATBOT EDUCATIVO                         │
│                  RAG con Supabase + Gemini                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │───▶│  FastAPI     │───▶│   Supabase   │
│  (HTML/JS)   │    │   Backend    │    │  (pgvector)  │
└──────────────┘    └──────────────┘    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │Google Gemini │
                    │  (LLM + AI)  │
                    └──────────────┘
```

### Componentes Principales

1. **Frontend** (`/frontend`)
   - Interfaz web estática (HTML, CSS, JavaScript)
   - Se comunica con FastAPI vía REST API

2. **Backend FastAPI** (`/app/main.py`)
   - Servidor API REST
   - Orquesta el sistema RAG con LlamaIndex
   - Gestiona embeddings y consultas
   - **Endpoint de ingesta**: `/api/v1/ingest` (nuevo)

3. **Ingestion Worker** (`/worker.py`) **[NUEVO]**
   - Servicio background persistente
   - Procesa jobs de ingesta de forma asíncrona
   - Polling cada 10 segundos
   - Elimina contenido antiguo (upsert)
   - Indexa nuevo contenido con metadata completa

4. **Supabase Vector Store** (`/app/supabase_vector_store.py`)
   - Custom vector store para LlamaIndex
   - Conecta vía API REST (no PostgreSQL directo)
   - Implementa búsqueda vectorial con pgvector
   - **Método delete_by_metadata**: Para upserts (nuevo)

5. **Supabase Database**
   - PostgreSQL con extensión pgvector
   - Almacena vectores (halfvec 3072 dims)
   - Función RPC para búsqueda de similitud
   - **Tabla ingestion_jobs**: Cola de trabajos (nueva)
   - **Función dequeue_ingestion_job()**: Dequeue atómico (nueva)

6. **Google Gemini**
   - **LLM**: `gemini-2.5-flash` para respuestas
   - **Embeddings**: `gemini-embedding-001` (3072 dims)

7. **Script de Ingesta Local** (`/ingest.py`)
   - Procesa documentos locales (PDF, TXT, MD, DOCX)
   - Genera embeddings
   - Inserta en Supabase
   - Para uso manual/batch

---

## 🔄 Flujo de Datos Completo

### 1. Flujo de Consulta del Usuario

```
┌─────────┐
│ Usuario │
└────┬────┘
     │ "¿Qué es el mantenimiento mecánico?"
     ▼
┌────────────────┐
│   Frontend     │ POST /api/chat
└────┬───────────┘
     │ {"question": "..."}
     ▼
┌────────────────────────────────────────────────────────┐
│              FastAPI Backend (main.py)                 │
│                                                        │
│  1. Recibe pregunta                                   │
│  2. Genera embedding con Gemini                       │
│     └─▶ Google Gemini API (gemini-embedding-001)     │
│                                                        │
│  3. Busca documentos similares                        │
│     └─▶ SupabaseVectorStore.query()                  │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────┐
│      SupabaseVectorStore (custom vector store)        │
│                                                        │
│  1. Recibe query_embedding (3072 dims)               │
│  2. Llama a RPC function vía API REST                │
│     POST /rest/v1/rpc/match_[table_name]             │
│  3. Recibe resultados (content + metadata)           │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────┐
│            Supabase (PostgreSQL + pgvector)           │
│                                                        │
│  1. Ejecuta función RPC                               │
│  2. Búsqueda vectorial con índice HNSW               │
│     embedding <=> query_embedding                     │
│  3. Retorna top K documentos similares               │
└─────────────┬──────────────────────────────────────────┘
              │ [{content, metadata, similarity}, ...]
              ▼
┌────────────────────────────────────────────────────────┐
│              FastAPI Backend (main.py)                 │
│                                                        │
│  4. Construye contexto con documentos recuperados     │
│  5. Genera respuesta con Gemini                       │
│     └─▶ Google Gemini API (gemini-2.5-flash)         │
│         + System prompt en español                     │
│         + Contexto de documentos                       │
│                                                        │
│  6. Retorna respuesta + fuentes                       │
└─────────────┬──────────────────────────────────────────┘
              │ {"answer": "...", "sources": [...]}
              ▼
┌────────────────┐
│   Frontend     │ Muestra respuesta al usuario
└────────────────┘
```

### 2. Flujo de Ingesta de Documentos

```
┌────────────┐
│ Documentos │ (PDF, TXT, MD, DOCX en /data)
└─────┬──────┘
      │
      ▼
┌────────────────────────────────────────────────────────┐
│               Script de Ingesta (ingest.py)            │
│                                                        │
│  1. Lee documentos desde /data                        │
│  2. Divide en chunks (512 tokens, overlap 20)         │
│  3. Genera embeddings por chunk                       │
│     └─▶ Google Gemini (gemini-embedding-001)         │
│  4. Inserta en Supabase                               │
│     └─▶ SupabaseVectorStore.add()                    │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────┐
│      SupabaseVectorStore (custom vector store)        │
│                                                        │
│  1. Por cada chunk:                                   │
│     POST /rest/v1/[table_name]                        │
│     {content, metadata, embedding}                     │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────┐
│            Supabase (PostgreSQL + pgvector)           │
│                                                        │
│  1. Inserta registros en tabla                        │
│  2. Almacena embeddings como halfvec(3072)           │
│  3. Índice HNSW indexa automáticamente               │
└────────────────────────────────────────────────────────┘
```

### 3. Flujo de Ingesta Asíncrona (API)

**Sistema de cola de jobs para ingesta de contenido desde sistemas externos**

```
┌─────────────────┐
│  Sistema        │ Sistema externo (CMS, LMS, etc.)
│  Externo        │
└────────┬────────┘
         │ POST /api/v1/ingest
         │ {unique_content_id, content, metadata...}
         ▼
┌────────────────────────────────────────────────────────┐
│          FastAPI Backend - Ingest Endpoint             │
│              (POST /api/v1/ingest)                     │
│                                                        │
│  1. Valida payload                                    │
│  2. Inserta job en ingestion_jobs table               │
│  3. Retorna 202 Accepted INMEDIATAMENTE               │
└─────────────┬──────────────────────────────────────────┘
              │
              │ ✅ 202 Accepted {job_id: 123}
              ▼
┌─────────────────┐
│  Sistema        │ Recibe confirmación instantánea
│  Externo        │
└─────────────────┘


         (Procesamiento Asíncrono)
              │
              ▼
┌────────────────────────────────────────────────────────┐
│          Supabase - ingestion_jobs Table               │
│                                                        │
│  id  | status     | payload              | created_at │
│  123 | pending    | {unique_id, ...}     | 10:00:00   │
│  124 | processing | {unique_id, ...}     | 10:00:01   │
│  125 | completed  | {unique_id, ...}     | 10:00:02   │
└─────────────┬──────────────────────────────────────────┘
              │
              │ Polling cada 10 segundos
              ▼
┌────────────────────────────────────────────────────────┐
│        Ingestion Worker (worker.py)                    │
│        Background Service - Persistent                 │
│                                                        │
│  Loop continuo:                                       │
│  1. Llama dequeue_ingestion_job() RPC                │
│     → Obtiene job "pending" más antiguo               │
│     → Actualiza a "processing" ATOMICAMENTE           │
│                                                        │
│  2. PROCESA JOB:                                      │
│     a) DELETE: Elimina chunks antiguos                │
│        vector_store.delete_by_metadata(               │
│          "unique_content_id", value                   │
│        )                                              │
│                                                        │
│     b) PREPARE: Crea Document con metadata            │
│        - content → texto principal                    │
│        - metadata → topic_id, version, title, etc.    │
│                                                        │
│     c) INDEX: Genera embeddings e inserta             │
│        VectorStoreIndex.from_documents([doc])         │
│        → Chunks → Embeddings → Supabase               │
│                                                        │
│  3. UPDATE: Actualiza estado del job                  │
│     → "completed" (éxito)                             │
│     → "failed" (error + error_message)                │
│                                                        │
│  4. REPEAT                                            │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────┐
│            Supabase Vector Store                       │
│                                                        │
│  Contenido indexado y listo para búsquedas            │
│  - Chunks con embeddings                              │
│  - Metadata completa para filtrado                    │
│  - unique_content_id para identificación              │
└────────────────────────────────────────────────────────┘
```

**Ventajas de este diseño:**

1. **Sin timeouts**: El sistema externo recibe 202 Accepted inmediatamente
2. **Escalable**: Múltiples workers pueden procesar jobs en paralelo
3. **Resiliente**: Si un worker falla, el job queda en "processing" y puede ser reseteado
4. **Trazable**: Cada job tiene ID único y estado rastreable
5. **Upsert automático**: El `unique_content_id` permite actualizar contenido existente

**Estructura del Payload:**

```json
{
  "unique_content_id": "course_123_topic_456",  // ID único para upsert
  "content": "Texto principal a indexar...",     // Contenido principal
  "course_slug": "mantenimiento-mecanico",       // Metadata
  "course_name": "Mantenimiento Mecánico",       // Metadata
  "topic_id": "topic_456",                       // Metadata (filtrable)
  "version": "1.0",                              // Metadata (filtrable)
  "title": "Introducción al Mantenimiento",      // Metadata (filtrable)
  "model": "standard",                           // Metadata
  "module": "Módulo 1",                          // Metadata
  "notes": "Versión inicial",                    // Metadata
  "version_data": "2025-01-15"                   // Metadata
}
```

**Componentes SQL Requeridos:**

1. **Tabla `ingestion_jobs`**: Cola de trabajos
2. **Función RPC `dequeue_ingestion_job()`**: Obtención atómica de jobs
3. **Índices**: Para performance en queries de estado
4. **Función `reset_stuck_jobs()`**: Para recuperar jobs atascados

Ver: `migrations/001_ingestion_jobs.sql` para scripts completos.

---

## 🔑 Puntos Críticos de Configuración

### 1. Conexión a Supabase (⚠️ IMPORTANTE)

**Problema Resuelto: IPv6 en Docker**

Docker por defecto no tiene IPv6 habilitado, pero Supabase puede requerir IPv6.

**Solución Implementada:**
- ✅ Usar **API REST de Supabase** en lugar de conexión directa PostgreSQL
- ✅ Cliente `httpx` directo (sin `supabase-py` para evitar conflictos de dependencias)
- ✅ Evita problemas de red IPv4/IPv6

```python
# NO usar: Conexión directa PostgreSQL (problemas IPv6)
# connection_string = "postgresql://..."

# SÍ usar: API REST de Supabase
supabase_url = "https://xxx.supabase.co"
supabase_key = "service_role_key"

vector_store = SupabaseVectorStore(
    supabase_url=supabase_url,
    supabase_key=supabase_key,
    # ...
)
```

### 2. Modelo de Embeddings (⚠️ CRÍTICO)

**Dimensiones Deben Coincidir:**

```
┌─────────────────────────────────────────────────────┐
│  Gemini Embedding Model: gemini-embedding-001       │
│  Genera: 3072 dimensiones                          │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Supabase Table Column: embedding halfvec(3072)    │
│  Almacena: 3072 dimensiones (half precision)       │
└─────────────────────────────────────────────────────┘
```

**⚠️ Si usas otro modelo, actualiza ambos lados:**
- `.env`: `EMBEDDING_MODEL` y `EMBEDDING_DIMENSIONS`
- Supabase: Columna `embedding halfvec(N)`

### 3. Índice HNSW (⚠️ ESENCIAL para Performance)

**Sin índice:**
- Búsqueda secuencial
- 6000 registros = 10+ segundos (TIMEOUT)

**Con índice HNSW:**
- Búsqueda aproximada
- 6000 registros = < 1 segundo

```sql
-- OBLIGATORIO ejecutar en Supabase:
CREATE INDEX idx_embedding_hnsw
ON [table_name]
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### 4. Función RPC de Supabase

**Estructura de la función:**

```sql
CREATE FUNCTION match_[table_name](
    query_embedding halfvec(3072),
    match_count integer DEFAULT 10,
    match_threshold double precision DEFAULT 0.5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (id bigint, content text, metadata jsonb, similarity double precision)
AS $$
    SELECT
        t.id,
        t.content,
        t.metadata,
        (1 - (t.embedding <=> query_embedding)) AS similarity
    FROM [table_name] t
    WHERE (1 - (t.embedding <=> query_embedding)) >= match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
$$;
```

**Puntos clave:**
- ✅ Usar operador `<=>` (cosine distance)
- ✅ Convertir a similarity: `1 - distance`
- ✅ Filtrar por `match_threshold`
- ✅ Ordenar por `similarity DESC`

### 5. System Prompt en Español

**Configuración en `app/main.py`:**

```python
qa_prompt_template = PromptTemplate(
    "Eres un asistente educativo experto...\n"
    "IMPORTANTE: Siempre responde en español...\n"
    "Contexto: {context_str}\n"
    "Pregunta: {query_str}\n"
    "Respuesta en español:"
)

query_engine = index.as_query_engine(
    text_qa_template=qa_prompt_template,
)
```

**Garantiza:**
- ✅ Respuestas siempre en español
- ✅ Tono educativo y profesional
- ✅ Uso correcto del contexto

### 6. Conflictos de Dependencias

**Problema:**
- `supabase-py 2.10.0` requiere `httpx < 0.28`
- `google-genai` requiere `httpx >= 0.28.1`
- ❌ Imposible instalar ambos

**Solución:**
- ✅ NO usar `supabase-py`
- ✅ Usar `httpx` directamente
- ✅ Implementar llamadas HTTP manualmente

```python
# Custom SupabaseVectorStore usa httpx directamente
client = httpx.Client(headers={...}, timeout=60.0)
response = client.post(f"{supabase_url}/rest/v1/rpc/{function}", json=params)
```

---

## 📁 Estructura de Archivos Clave

```
chatbot/
├── app/
│   ├── main.py                      # FastAPI backend + RAG logic
│   └── supabase_vector_store.py     # Custom vector store (httpx)
│
├── frontend/                         # Frontend estático
│   ├── index.html
│   └── ...
│
├── data/                            # Documentos para ingesta
│   └── *.pdf, *.txt, *.md
│
├── ingest.py                        # Script de ingesta de documentos
├── requirements.txt                 # Dependencias Python
├── .env                            # Variables de entorno (NO en git)
├── .env.example                    # Template de configuración
├── docker-compose.yml              # Orquestación Docker
└── Dockerfile                      # Imagen de la app

```

---

## 🔐 Variables de Entorno Críticas

```bash
# Google AI
GOOGLE_API_KEY="..."                 # API key de Google AI Studio

# Supabase API REST
SUPABASE_URL="https://xxx.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJ..."   # Service role key (SECRET!)
SUPABASE_TABLE_NAME="table_name"
SUPABASE_RPC_FUNCTION="match_table_name"

# Embeddings
EMBEDDING_MODEL="models/gemini-embedding-001"
EMBEDDING_DIMENSIONS=3072

# RAG Config
SIMILARITY_TOP_K=3
MATCH_THRESHOLD=0.5
CHUNK_SIZE=512
CHUNK_OVERLAP=20

# LLM
GEMINI_MODEL="models/gemini-2.5-flash"
```

---

## 🚀 Comandos Esenciales

### Desarrollo

```bash
# Construir y levantar servicios (API + Worker)
docker compose build
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f fastapi_app        # Logs de la API
docker compose logs -f ingestion_worker    # Logs del worker

# Ver logs de ambos servicios
docker compose logs -f

# Reiniciar servicios
docker compose restart fastapi_app         # Reiniciar API
docker compose restart ingestion_worker    # Reiniciar worker

# Detener todo
docker compose down
```

### Ingesta de Documentos

**Opción 1: Ingesta Local (archivos en /data)**

```bash
# Copiar documentos a /data primero, luego:
docker compose run --rm fastapi_app python ingest.py
```

**Opción 2: Ingesta Asíncrona (API desde sistema externo)**

```bash
# Enviar contenido para indexación
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "unique_content_id": "course_123_topic_456",
    "course_slug": "mantenimiento-mecanico",
    "course_name": "Mantenimiento Mecánico Automotriz",
    "topic_id": "topic_456",
    "model": "standard",
    "version": "1.0",
    "title": "Introducción al Mantenimiento",
    "module": "Módulo 1",
    "notes": "Versión inicial",
    "version_data": "2025-01-15",
    "content": "El mantenimiento mecánico automotriz es fundamental para..."
  }'

# Respuesta esperada (202 Accepted):
# {"message": "Content received and queued for processing.", "job_id": 123}
```

**Monitorear Jobs de Ingesta:**

```bash
# Consultar estado de jobs en Supabase SQL Editor
SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT 10;

# Ver estadísticas de jobs
SELECT * FROM ingestion_jobs_stats;

# Resetear jobs atascados (si un worker crasheó)
SELECT reset_stuck_jobs(30);  -- Jobs en "processing" por más de 30 min
```

### Testing

```bash
# Health check
curl http://localhost:8080/health

# Consulta de prueba al chatbot
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Qué es el mantenimiento mecánico?"}'

# Test de ingesta asíncrona
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "unique_content_id": "test_123",
    "course_slug": "test-course",
    "course_name": "Test Course",
    "topic_id": "topic_1",
    "model": "test",
    "version": "1.0",
    "title": "Test Content",
    "module": "Module 1",
    "notes": "Test",
    "version_data": "2025-01-15",
    "content": "Este es un contenido de prueba para validar la ingesta asíncrona."
  }'
```

---

## 🐛 Troubleshooting

### Error: "Network unreachable" (IPv6)
**Causa:** Docker intentando conectar a Supabase vía IPv6
**Solución:** ✅ Ya implementada - usar API REST en lugar de PostgreSQL directo

### Error: "Statement timeout" en RPC
**Causa:** Falta índice HNSW en tabla
**Solución:** Ejecutar SQL de creación de índice en Supabase

### Error: "Conflicto de dependencias httpx"
**Causa:** `supabase-py` y `google-genai` requieren versiones incompatibles
**Solución:** ✅ Ya implementada - usar `httpx` directamente sin `supabase-py`

### Error: "Field required: stores_text"
**Causa:** `BasePydanticVectorStore` requiere campos específicos
**Solución:** ✅ Ya implementada - campos declarados correctamente

### Respuestas en inglés
**Causa:** Gemini responde en el idioma detectado
**Solución:** ✅ Ya implementada - system prompt fuerza español

### Worker no procesa jobs (Async Ingestion)
**Causa:** El worker no está corriendo o falló al iniciar
**Solución:**
```bash
# Verificar que el worker esté corriendo
docker compose ps

# Ver logs del worker
docker compose logs -f ingestion_worker

# Reiniciar el worker
docker compose restart ingestion_worker
```

### Jobs quedan en estado "processing" indefinidamente
**Causa:** El worker crasheó mientras procesaba un job
**Solución:**
```sql
-- Resetear jobs atascados (en Supabase SQL Editor)
SELECT reset_stuck_jobs(30);  -- Jobs en processing > 30 minutos
```

### Error: "Table ingestion_jobs does not exist"
**Causa:** No se ejecutaron los scripts SQL de migración
**Solución:** Ejecutar `migrations/001_ingestion_jobs.sql` en Supabase SQL Editor

### Error: "Function dequeue_ingestion_job does not exist"
**Causa:** No se creó la función RPC en Supabase
**Solución:** Ejecutar `migrations/001_ingestion_jobs.sql` en Supabase SQL Editor

### Jobs fallan con error "delete_by_metadata"
**Causa:** La versión de SupabaseVectorStore no tiene el método delete_by_metadata
**Solución:** Verificar que `app/supabase_vector_store.py` tenga el método implementado

### Contenido duplicado después de re-indexar
**Causa:** El unique_content_id no es único o el delete falló
**Solución:**
```sql
-- Verificar chunks duplicados (en Supabase SQL Editor)
SELECT metadata->>'unique_content_id' as content_id, COUNT(*) as count
FROM [tu_tabla]
GROUP BY metadata->>'unique_content_id'
HAVING COUNT(*) > 10;

-- Eliminar chunks duplicados manualmente si es necesario
DELETE FROM [tu_tabla]
WHERE metadata->>'unique_content_id' = 'content_id_duplicado';
```

---

## 📊 Métricas de Performance

| Métrica | Sin Optimizar | Optimizado |
|---------|---------------|------------|
| Búsqueda vectorial | 10+ seg (timeout) | < 1 seg |
| Generación de respuesta | 2-3 seg | 2-3 seg |
| **Total end-to-end** | ❌ Falla | ✅ 3-4 seg |

**Optimizaciones aplicadas:**
- ✅ Índice HNSW en Supabase
- ✅ Conexión vía API REST (más estable)
- ✅ Cache de embeddings en LlamaIndex

---

## 🔧 Setup: Ingesta Asíncrona (API)

Para habilitar el sistema de ingesta asíncrona desde sistemas externos:

### 1. Ejecutar Migración SQL en Supabase

1. Abre el **SQL Editor** en tu dashboard de Supabase
2. Copia y pega el contenido completo de `migrations/001_ingestion_jobs.sql`
3. Ejecuta el script (Run)
4. Verifica que se crearon:
   - ✅ Tabla `ingestion_jobs`
   - ✅ Índices (`idx_ingestion_jobs_pending`, etc.)
   - ✅ Función `dequeue_ingestion_job()`
   - ✅ Función `reset_stuck_jobs()`
   - ✅ Vista `ingestion_jobs_stats`

### 2. Verificar Configuración en .env

Asegúrate de tener estas variables configuradas:

```bash
# Supabase (ya configuradas para el chatbot)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_TABLE_NAME=tu_tabla

# Google AI (ya configuradas)
GOOGLE_API_KEY=...

# Worker (opcional, tiene defaults)
WORKER_POLL_INTERVAL=10  # Segundos entre polls
```

### 3. Levantar los Servicios

```bash
# Construir y levantar API + Worker
docker compose build
docker compose up -d

# Verificar que ambos servicios estén corriendo
docker compose ps

# Deberías ver:
# - fastapi_service (running)
# - ingestion_worker_service (running)
```

### 4. Verificar que el Worker está funcionando

```bash
# Ver logs del worker
docker compose logs -f ingestion_worker

# Deberías ver:
# 🚀 INGESTION WORKER STARTED
# ✅ Todas las variables de entorno están configuradas
# ✅ LlamaIndex configurado correctamente
# ✅ Conexión a Supabase establecida
# 👀 Esperando por nuevos jobs...
```

### 5. Probar el Sistema

```bash
# Enviar un job de prueba
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "unique_content_id": "test_001",
    "course_slug": "test",
    "course_name": "Test Course",
    "topic_id": "1",
    "model": "test",
    "version": "1.0",
    "title": "Prueba de Ingesta",
    "module": "Module 1",
    "notes": "Test",
    "version_data": "2025-01-15",
    "content": "Este es contenido de prueba para verificar que el sistema funciona correctamente."
  }'

# Deberías recibir:
# HTTP 202 Accepted
# {"message": "Content received and queued for processing.", "job_id": 1}

# Ver el procesamiento en logs del worker
docker compose logs -f ingestion_worker

# Deberías ver:
# 📥 Job #1 obtenido: ID=1
# 🚀 Procesando job 1 para unique_content_id: test_001
# 🗑️  Eliminando contenido antiguo...
# ✅ 0 chunk(s) antiguo(s) eliminado(s)
# 📄 Documento creado con 95 caracteres
# 🔍 Indexando nuevo contenido...
# ✅ Contenido indexado exitosamente para test_001
# ✅ Job 1 actualizado a estado: completed
```

### 6. Monitorear Jobs

**Desde Supabase SQL Editor:**

```sql
-- Ver todos los jobs recientes
SELECT
  id,
  status,
  payload->>'unique_content_id' as content_id,
  payload->>'title' as title,
  created_at,
  error_message
FROM ingestion_jobs
ORDER BY created_at DESC
LIMIT 20;

-- Ver estadísticas
SELECT * FROM ingestion_jobs_stats;
```

**Desde la línea de comandos:**

```bash
# Ver logs del worker en tiempo real
docker compose logs -f ingestion_worker

# Ver logs de la API (para ver los POST requests)
docker compose logs -f fastapi_app
```

### 7. Integración con Sistema Externo

Tu sistema externo debe hacer un POST request a:

```
POST http://tu-servidor:8080/api/v1/ingest
Content-Type: application/json

{
  "unique_content_id": "string (requerido, único por contenido)",
  "content": "string (requerido, texto a indexar)",
  "course_slug": "string",
  "course_name": "string",
  "topic_id": "string",
  "model": "string",
  "version": "string",
  "title": "string",
  "module": "string",
  "notes": "string",
  "version_data": "string"
}
```

**Respuesta esperada:**
- Status: `202 Accepted`
- Body: `{"message": "Content received and queued for processing.", "job_id": 123}`

**Notas importantes:**
- El `unique_content_id` debe ser único por contenido
- Si envías el mismo `unique_content_id` dos veces, el contenido viejo será reemplazado
- El procesamiento es asíncrono, puede tomar desde segundos hasta minutos dependiendo del tamaño
- Verifica el estado del job consultando la tabla `ingestion_jobs` en Supabase

---

## 🎯 Próximos Pasos Opcionales

1. **Mejoras de Performance:**
   - Implementar cache de consultas frecuentes
   - Usar streaming en respuestas del LLM
   - Optimizar tamaño de chunks

2. **Mejoras de UX:**
   - Agregar typing indicator en frontend
   - Mostrar fuentes clickeables
   - Implementar historial de conversación

3. **Monitoreo:**
   - Agregar logging estructurado
   - Métricas de latencia y uso
   - Alertas de errores

4. **Seguridad:**
   - Rate limiting en API
   - Validación de inputs
   - Sanitización de respuestas

---

## 📚 Referencias

- **LlamaIndex Docs:** https://docs.llamaindex.ai/
- **Supabase pgvector:** https://supabase.com/docs/guides/ai/vector-columns
- **Google Gemini API:** https://ai.google.dev/
- **FastAPI Docs:** https://fastapi.tiangolo.com/

---

*Última actualización: 2025-11-06*
*Stack: FastAPI + LlamaIndex + Supabase (pgvector) + Google Gemini*
*Features: RAG Chatbot + Async Content Ingestion API*
