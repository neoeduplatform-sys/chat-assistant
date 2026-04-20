# Modelo de memoria conversacional en 3 capas (especificación ejecutable)

Este documento describe **qué** implementar, **por qué** y **en qué orden**, para que una IA o un desarrollador pueda implementar el comportamiento sin ambigüedad. Está alineado con el backend actual: **FastAPI** (`app/main.py`), endpoint **`POST /api/chat`**, modelo **`ChatRequest`** (`app/models.py`) con `course_id` y `user_id`, y **RAG** vía **Supabase pgvector** + **Gemini**.

---

## 1. Objetivo

Permitir conversaciones **hiladas** (no solo pregunta-respuesta aislada) para explicaciones técnicas **medianas o largas**, manteniendo:

1. **Continuidad inmediata** (últimos mensajes, con techo de tokens).
2. **Continuidad a medio plazo** (resumen acumulado por usuario y curso).
3. **Conocimiento del curso** vía **RAG** (documentos indexados), **sin confundir** el historial con el material del curso.

**Clave compuesta de negocio:** `(user_id, course_id)`.

---

## 2. Las tres capas (definiciones obligatorias)

| Capa | Nombre | Qué contiene | Rol en el prompt |
|------|--------|----------------|------------------|
| **A** | Historial reciente con techo de tokens | Mensajes literales `user` / `assistant` ordenados por tiempo | Coherencia inmediata (“seguimos con el ejemplo…”, referencias al turno anterior) |
| **B** | Resumen acumulado | Un texto breve derivado de conversaciones pasadas de ese usuario en ese curso | Recordar acuerdos/definiciones ya dados cuando el historial ya no cabe |
| **C** | RAG del curso | Chunks recuperados por similitud del **vector store del curso** (tabla/RPC según `course_id`) | Hechos técnicos del material oficial |

**Regla de oro:** La capa **C** responde a “qué dice el material del curso”. Las capas **A** y **B** responden a “qué está pasando en **esta** conversación con **este** usuario en **este** curso”. No sustituyen una a la otra.

---

## 3. Comportamiento cuando falta `user_id`

- Si **`user_id` es `null` o vacío:** el servidor **no** persiste ni recupera capas A ni B; solo ejecuta **capa C (RAG)** como hoy.
- Si **`user_id` está presente:** se cargan A y B (si existen en almacenamiento), se construye el prompt completo, se genera la respuesta, y **después** se persisten el mensaje del usuario y la respuesta del asistente para el siguiente turno.

*(Regla: rechazar el chat con memoria si no hay `user_id`.)*

---

## 4. Modelo de datos (Supabase / PostgreSQL)

Implementar **persistencia** en la misma base que ya usáis (Supabase):

### 4.1 Tabla `chat_conversations`

Representa un hilo por usuario y curso (un hilo activo por `(user_id, course_id)` es el caso más simple).

| Columna | Tipo | Notas |
|---------|------|--------|
| `id` | `uuid` PK | Generado por servidor o DB |
| `user_id` | `text` NOT NULL | Identificador estable del usuario (externo a la app) |
| `course_id` | `text` NOT NULL | Mismo formato que `ChatRequest.course_id` |
| `created_at` | `timestamptz` DEFAULT now() | |
| `updated_at` | `timestamptz` | Actualizar en cada mensaje |

**Restricción:** `UNIQUE (user_id, course_id)` para permitir **un** hilo activo por usuario y curso.

### 4.2 Tabla `chat_messages`

| Columna | Tipo | Notas |
|---------|------|--------|
| `id` | `bigserial` PK | |
| `conversation_id` | `uuid` NOT NULL FK → `chat_conversations.id` | |
| `role` | `text` NOT NULL | Valores permitidos: `user`, `assistant` |
| `content` | `text` NOT NULL | Texto completo del mensaje |
| `created_at` | `timestamptz` DEFAULT now() | Orden cronológico |

**Índice:** `(conversation_id, created_at DESC)` para leer rápido los últimos mensajes.

### 4.3 Tabla `user_course_memory` (capa B)

| Columna | Tipo | Notas |
|---------|------|--------|
| `user_id` | `text` NOT NULL | |
| `course_id` | `text` NOT NULL | |
| `summary` | `text` NOT NULL | Resumen acumulado en español |
| `updated_at` | `timestamptz` | |
| `message_count_at_last_summary` | `integer` | Opcional: para política de cuándo refrescar |

**PK compuesta:** `(user_id, course_id)`.

---

## 5. Contrato HTTP (extensión sobre el estado actual)

**Estado actual** (`app/models.py`): `ChatRequest` incluye `question`, `course_id`, `user_id`.

**Extensiones recomendadas para implementación completa:**

- `user_id`:  **requerido** para memoria A/B.
- `course_id` **requerido** siendo que debe existir una conversacion por usuario para cada curso, con `user_id` y `cource_id` inferir el id de `course_id`


---

## 6. Variables de entorno (propuestas)

Definir en `.env` y documentar en `.env.example`:

| Variable | Ejemplo | Significado |
|----------|---------|-------------|
| `CHAT_HISTORY_MAX_TOKENS` | `3500` | Techo de tokens para **capa A** (solo historial literal) |
| `CHAT_SUMMARY_MAX_TOKENS` | `800` | Techo aproximado para inyectar **capa B** en el prompt |
| `CHAT_SUMMARY_REFRESH_EVERY_N_TURNS` | `6` | Cada cuántos **turnos** (user+assistant) regenerar/actualizar resumen |
| `CHAT_MAX_MESSAGES_SAFETY` | `40` | Tope duro de mensajes a considerar antes del recorte por tokens (evitar loops) |

Los valores deben ajustarse al **modelo** y al espacio que dejéis para **capa C** y la respuesta.

---

## 7. Algoritmo por request (orden estricto)

Para cada `POST /api/chat` con `user_id` presente:

### Paso 1 — Resolver conversación

1. Buscar `chat_conversations` por `(user_id, course_id)`.
2. Si no existe, **insertar** una fila y usar su `id` como `conversation_id`.

### Paso 2 — Cargar capa B (resumen)

1. `SELECT summary FROM user_course_memory WHERE user_id = ? AND course_id = ?`.
2. Si no hay fila, `summary = ""` (cadena vacía).

### Paso 3 — Cargar capa A (historial)

1. `SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY created_at ASC` (o leer últimos N con subconsulta según índice).
2. **Construir lista** de mensajes en orden cronológico.
3. **Recortar desde el final hacia atrás** por **tokens estimados** hasta `CHAT_HISTORY_MAX_TOKENS`, sin romper pares `user`/`assistant` si es posible (si el último mensaje cortado es `user` sin `assistant`, descartar ese par incompleto).
4. Si la lista está vacía (primera interacción), la capa A no aporta texto.

### Paso 4 — Persistir el mensaje del usuario (antes de llamar al LLM)

1. `INSERT` en `chat_messages` con `role = 'user'` y `content = question`.



### Paso 5 — Capa C (RAG) — **igual que el flujo actual**

1. Resolver configuración del curso (`get_course_config_service().get_course_config(course_id)`).
2. Instanciar `SupabaseVectorStore` con `table_name` y `rpc_function` del curso.
3. `VectorStoreIndex.from_vector_store`, `as_query_engine`, etc.

**Importante:** La **pregunta** enviada al query engine para recuperar nodos puede ser:

- Solo `question`, o
- `question` enriquecida con un **prefijo** muy corto del resumen (opcional, avanzado). No mezclar el historial completo en el embedding de búsqueda.

### Paso 6 — Construcción del prompt final para el LLM

Orden recomendado de bloques (todos en español si el producto lo exige):

1. **Instrucciones del sistema** (asistente educativo, tono, “responde en español”, etc.).
2. **Capa B — Resumen** (si no vacío):  
   `"Resumen de la conversación previa con este estudiante en este curso:\n{summary}\n"`
3. **Capa A — Historial reciente** (si no vacío):  
   Formato tipo chat: `Usuario: ...` / `Asistente: ...` solo para los mensajes incluidos tras el recorte por tokens.
4. **Capa C — Contexto RAG**: el `context_str` que ya arma LlamaIndex a partir de los nodos recuperados (equivalente a lo que hoy va en `qa_prompt_template` como `"{context_str}"`).
5. **Pregunta actual**: `question`.

**Implementación concreta en este repo:** hoy el `query_engine` usa `text_qa_template` con `{context_str}` y `{query_str}`. Para las capas A y B:

- ** Construir un único `query_str` compuesto:  
  `[resumen opcional][historial opcional]\n\nPregunta actual: {question}`  
  y dejar `{context_str}` solo para RAG.

### Paso 7 — Llamada al modelo y extracción de respuesta

1. Ejecutar la consulta (como `course_query_engine.query(...)` con `query_str` compuesto).
2. Obtener `answer` como string.

### Paso 8 — Persistir respuesta del asistente

1. `INSERT` en `chat_messages` con `role = 'assistant'` y `content = answer`.

### Paso 9 — Actualizar resumen (capa B) según política

Si el número de **turnos** nuevos desde el último resumen ≥ `CHAT_SUMMARY_REFRESH_EVERY_N_TURNS` (o si el historial recortado supera umbral):

1. Llamar al LLM con un prompt **solo de resumen**, por ejemplo:  
   - Entrada: últimos K mensajes o el resumen anterior + últimos mensajes.  
   - Salida: nuevo `summary` conciso (≤ `CHAT_SUMMARY_MAX_TOKENS` objetivo).
2. `UPSERT` en `user_course_memory`.

Este paso puede ser **asíncrono** (cola/job) para no aumentar latencia del chat; si es así, documentar consistencia eventual.

---

## 8. Estimación de tokens

- Preferir librería compatible con el tokenizer del modelo (o estimación `chars/4` solo como fallback documentado).
- El recorte **siempre** aplica primero a **capa A**; la capa B ya está acotada por diseño.

---

## 9. Integración con el código existente (puntos de anclaje)

| Ubicación | Qué tocar |
|-----------|-----------|
| `app/models.py` | `course_id` en request/response; hacer `user_id` requerido. Utilizar ambos para obtener entidad `converstation`  |
| `app/main.py` → `chat_endpoint` | Antes de `course_query_engine.query`: cargar A+B; construir `query_str`; después de respuesta: guardar mensajes y actualizar resumen |
| Nuevo módulo sugerido | `app/conversation_memory.py` o `app/chat_memory_service.py`: CRUD Supabase, recorte por tokens, refresh de resumen |
| Supabase | Ejecutar SQL de sección 4 en SQL Editor o migración versionada |

El **RAG por curso** ya está en `chat_endpoint` (líneas que crean `SupabaseVectorStore` con `course_config['table_name']` y `rpc_function`, que den salir de la tabla de configuración `course_configurations`); la memoria A/B es **adicional** y **previa/superpuesta** al template de QA.

---

## 10. Criterios de aceptación (verificables)

1. Mismo `user_id` + `course_id`: segunda pregunta referencial (“¿y eso cómo se relaciona con lo anterior?”) recibe respuesta coherente **usando capa A o B**, sin depender solo del RAG.
2. Cambiar `course_id` con el mismo `user_id`: **no** se mezcla resumen ni mensajes de otro curso.
3. Con `user_id` ausente: comportamiento idéntico al actual (solo RAG).
4. Mensajes muy largos: no se excede el presupuesto de contexto gracias al recorte por tokens en capa A.
5. Las tablas crecen de forma acotada por política (opcional: job de archivado).

---

## 11. Lo que este modelo **no** es

- No reemplaza el **control de acceso**: validar identidad de `user_id` en el borde (API gateway, JWT, etc.) si el dato es sensible.
- No es “memoria infinita perfecta”: el resumen pierde detalle; por eso conviven A + B + C.

---

## 12. Referencias internas del repo

- Endpoint: `POST /api/chat` en `app/main.py`
- Request/response: `ChatRequest`, `ChatResponse` en `app/models.py`
- RAG y vector store: `app/supabase_vector_store.py`, `app/course_config.py`
- Arquitectura general: `CLAUDE.md`

