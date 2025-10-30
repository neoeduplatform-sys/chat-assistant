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

3. **Supabase Vector Store** (`/app/supabase_vector_store.py`)
   - Custom vector store para LlamaIndex
   - Conecta vía API REST (no PostgreSQL directo)
   - Implementa búsqueda vectorial con pgvector

4. **Supabase Database**
   - PostgreSQL con extensión pgvector
   - Almacena vectores (halfvec 3072 dims)
   - Función RPC para búsqueda de similitud

5. **Google Gemini**
   - **LLM**: `gemini-2.5-flash` para respuestas
   - **Embeddings**: `gemini-embedding-001` (3072 dims)

6. **Script de Ingesta** (`/ingest.py`)
   - Procesa documentos (PDF, TXT, MD, DOCX)
   - Genera embeddings
   - Inserta en Supabase

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
# Construir y levantar servicios
docker compose build
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f fastapi_app

# Reiniciar servicio
docker compose restart fastapi_app

# Detener todo
docker compose down
```

### Ingesta de Documentos

```bash
# Copiar documentos a /data primero, luego:
docker compose run --rm fastapi_app python ingest.py
```

### Testing

```bash
# Health check
curl http://localhost:8080/health

# Consulta de prueba
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Qué es el mantenimiento mecánico?"}'
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

*Última actualización: 2025-10-29*
*Stack: FastAPI + LlamaIndex + Supabase (pgvector) + Google Gemini*
