# Cohere Rerank — guía ejecutable por agentes (IA / automatización)

**Audiencia:** sistemas automatizados, asistentes de código u otras IA que deben **implementar** el rerank de Cohere sin ambigüedad.

**Objetivo:** añadir **Cohere Rerank** como postprocesador de nodos de LlamaIndex **después** de la recuperación vectorial en Supabase y **antes** de enviar el contexto al LLM (Gemini). No cambiar embeddings, tabla pgvector ni lógica de ingesta salvo lo indicado.

**Idioma:** las instrucciones imperativas y los identificadores están en inglés donde es estándar (`query_engine`, `node_postprocessors`). Las explicaciones breves pueden leerse en español.

---

## 0. Contract for automated execution (read first)

| Field | Value |
|-------|--------|
| **Repository root** | Directory containing `app/main.py`, `requirements.txt`, `docker-compose.yml`. |
| **Files to modify** | `requirements.txt`, `app/main.py`, optionally `.env.example`. **Recommended:** new file `app/cohere_rerank.py`. |
| **Files NOT to modify** | `app/supabase_vector_store.py` (unless extending `filter`; out of scope here), `worker.py` (indexing only; no query engine). |
| **Must preserve** | Behavior when rerank is **disabled**: same retrieval as today using `SIMILARITY_TOP_K` only. |
| **Must duplicate logic** | Any change to `as_query_engine(...)` MUST appear in **both** call sites listed in section 2. |
| **Stop condition** | Implementation is complete when: dependency installed, env vars documented, both call sites updated, `pip check` or import succeeds, `/health` returns 200. |

---

## 1. Repository facts (do not guess)

Use these **exact** locations:

| Item | Path / anchor |
|------|----------------|
| Global query engine init | Function `async def initialize_query_engine():` in `app/main.py` |
| First `as_query_engine` | Inside `initialize_query_engine`, block that assigns to `query_engine = index.as_query_engine(` (currently ~lines 246–250) |
| Per-course chat | `POST /api/chat` handler; variable `course_query_engine = index.as_query_engine(` (currently ~lines 439–443) |
| Retrieval env vars today | `MATCH_THRESHOLD`, `SIMILARITY_TOP_K` read via `os.getenv` in the chat handler (~406–407) and in `initialize_query_engine` (~186–187) |
| Docker API service | `docker-compose.yml` service name: `fastapi_app` (builds `Dockerfile`) |

**Search strings (unique anchors for search/replace):**

- Anchor A: `query_engine = index.as_query_engine(`
- Anchor B: `course_query_engine = index.as_query_engine(`

---

## 2. Environment variables (specification)

Add to **`.env`** (secrets never committed). Add **placeholders** to `.env.example` without real keys.

| Variable | Required when rerank ON | Default / fallback | Semantics |
|----------|-------------------------|--------------------|-----------|
| `COHERE_RERANK_ENABLED` | Yes | `false` | Rerank runs only if value is one of: `1`, `true`, `yes` (case-insensitive). |
| `COHERE_API_KEY` | Yes | empty | Cohere API key. If enabled but missing, implementation must **not** crash: skip rerank and log warning. |
| `COHERE_RERANK_MODEL` | No | `rerank-v3.5` | Pass to `CohereRerank(model=...)`. **Agent must** open PyPI or installed package doc if import fails. |
| `RERANK_TOP_N` | No | `4` | `top_n` for Cohere rerank (final nodes for LLM). |
| `VECTOR_RETRIEVAL_K` | No | fallback chain below | Used as `similarity_top_k` **only when** rerank is active. |

**Retrieval count rule (normative):**

```
IF cohere_rerank_active:
    retrieval_k = int(os.getenv("VECTOR_RETRIEVAL_K", os.getenv("SIMILARITY_TOP_K", "10")))
ELSE:
    retrieval_k = int(os.getenv("SIMILARITY_TOP_K", "3"))
```

**Invariant:** `retrieval_k >= RERANK_TOP_N` whenever rerank is active. If not, clamp: `retrieval_k = max(retrieval_k, RERANK_TOP_N)`.

---

## 3. Dependency

**File:** `requirements.txt`

**Action:** append exactly one line (preserve existing pins style if present):

```text
llama-index-postprocessor-cohere-rerank>=0.5.0
```

**Verify (local):**

```bash
pip install -r requirements.txt
python -c "from llama_index.postprocessor.cohere_rerank import CohereRerank; print('ok')"
```

If import path differs in installed version, read package `llama_index.postprocessor.cohere_rerank` or PyPI README and **adjust import only** — do not change Supabase code.

---

## 4. New module (recommended for agents)

**Create file:** `app/cohere_rerank.py`

**Requirements:**

1. Export a function: `build_cohere_rerank_postprocessors() -> list` (empty list means no rerank).
2. Enable rerank only if `COHERE_RERANK_ENABLED` is truthy **and** `COHERE_API_KEY` is non-empty.
3. On **any** exception during import or instantiation, log `logger.warning` with exception message and return `[]` (fail-open).
4. Use lazy import: `from llama_index.postprocessor.cohere_rerank import CohereRerank` inside the function or inside `try`, so missing optional dependency in edge builds fails gracefully if you choose to make it optional (recommended: keep dependency in requirements).

**Reference implementation (agent may copy and adjust constructor kwargs to match installed library version):**

```python
import logging
import os
from typing import List


logger = logging.getLogger(__name__)


def _cohere_rerank_enabled() -> bool:
    v = os.getenv("COHERE_RERANK_ENABLED", "false").lower()
    return v in ("1", "true", "yes")


def is_rerank_active() -> bool:
    """True iff rerank should run: flag on and API key present."""
    if not _cohere_rerank_enabled():
        return False
    return bool(os.getenv("COHERE_API_KEY", "").strip())


def build_cohere_rerank_postprocessors() -> List:
    if not is_rerank_active():
        return []
    api_key = os.getenv("COHERE_API_KEY")  # set when is_rerank_active()
    try:
        from llama_index.postprocessor.cohere_rerank import CohereRerank
    except ImportError as e:
        logger.warning("Cohere rerank package not available: %s", e)
        return []

    top_n = int(os.getenv("RERANK_TOP_N", "4"))
    model = os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5")
    try:
        return [CohereRerank(api_key=api_key, top_n=top_n, model=model)]
    except Exception as e:
        logger.warning("Failed to build CohereRerank: %s", e)
        return []
```

**Helper for retrieval_k (same module `app/cohere_rerank.py`, import from `app/main.py`):**

```python
def effective_similarity_top_k() -> int:
    if not is_rerank_active():
        return int(os.getenv("SIMILARITY_TOP_K", "3"))
    k = int(os.getenv("VECTOR_RETRIEVAL_K", os.getenv("SIMILARITY_TOP_K", "10")))
    n = int(os.getenv("RERANK_TOP_N", "4"))
    return max(k, n)
```

**Note:** `is_rerank_active()` is the single source of truth for “rerank on + key present”.

---


## 5. Modify `app/main.py` (two mandatory edits)

### 5.1 Imports

Add:

```python
from app.cohere_rerank import build_cohere_rerank_postprocessors, effective_similarity_top_k
```

### 5.2 Replace `initialize_query_engine` block

**Find:** assignment to `query_engine = index.as_query_engine(`

**Set:**

- `similarity_top_k=effective_similarity_top_k()` OR inline equivalent per section 2.
- `node_postprocessors=build_cohere_rerank_postprocessors()`

**Keep:** `streaming=False`, `text_qa_template=qa_prompt_template` unchanged unless explicitly required.

### 5.3 Replace `/api/chat` block

**Find:** `course_query_engine = index.as_query_engine(`

**Apply:** **identical** `similarity_top_k` and `node_postprocessors` as in 5.2.

**Logging (recommended):** after building postprocessors, log at INFO whether rerank list is empty or not (boolean), without printing API keys.

---

## 6. Docker

**Action:** rebuild the image that runs `app.main`:

```bash
docker compose build fastapi_app
docker compose up -d fastapi_app
```

Service `ingestion_worker` uses the same `Dockerfile` in this repo; adding a package is acceptable; worker does not need to call Cohere.

---

## 7. Verification checklist (agent must execute)

| Step | Command / action | Expected |
|------|-------------------|----------|
| V1 | `python -c "from app.cohere_rerank import build_cohere_rerank_postprocessors; print(build_cohere_rerank_postprocessors())"` with `COHERE_RERANK_ENABLED=false` | `[]` |
| V2 | Start API; `GET /health` | HTTP 200 |
| V3 | `POST /api/chat` with valid `course_id` | JSON with `answer`; no 500 |
| V4 | With `COHERE_RERANK_ENABLED=true` and invalid key | No crash; warning in logs; chat still returns 200 (fail-open) |

---

## 8. Rollback

1. Set `COHERE_RERANK_ENABLED=false` in `.env`.
2. Optionally remove `node_postprocessors` and restore `similarity_top_k` to `int(os.getenv("SIMILARITY_TOP_K", "3"))` only.
3. Remove `llama-index-postprocessor-cohere-rerank` from `requirements.txt` if dependency must be eliminated.

---

## 9. Non-goals (do not do unless asked)

- Do not change `MATCH_THRESHOLD` semantics in SQL.
- Do not send user PII to Cohere beyond question + retrieved chunks (privacy review is human responsibility).
- Do not add Cohere to `worker.py` ingestion pipeline.

---

## 10. Human references

- [llama-index-postprocessor-cohere-rerank (PyPI)](https://pypi.org/project/llama-index-postprocessor-cohere-rerank/)
- Cohere Rerank API / model list: official Cohere documentation.

---

*Version: structured for automated execution. Update anchors if `main.py` line numbers shift; use search strings in section 1.*

