# Qué es y qué contiene `COHERE_RERANK_STEP_BY_STEP.md`

Este archivo **no sustituye** la guía técnica: sirve para **humanos** (y como mapa mental para IA) que quieren entender **de un vistazo** el propósito de cada parte del documento [`COHERE_RERANK_STEP_BY_STEP.md`](./COHERE_RERANK_STEP_BY_STEP.md).

---


## Propósito del documento principal

`COHERE_RERANK_STEP_BY_STEP.md` está redactado como **procedimiento ejecutable**: está pensado para que un asistente de código u otra IA pueda **implementar** la integración de Cohere como **reranker** (reordenador de fragmentos tras la búsqueda vectorial) **sin ambigüedad**.

- **Qué hace el rerank en este proyecto:** los fragmentos ya recuperados desde Supabase se envían a Cohere para **ordenarlos por relevancia** respecto a la pregunta; solo los mejores pasan al modelo Gemini.
- **Qué no cubre esa guía por defecto:** cambiar embeddings, migrar la base vectorial ni reescribir la ingesta (salvo lo que explícitamente se indique allí).

---

## Relación con otros documentos

| Archivo | Rol |
|---------|-----|
| [`COHERE_INTEGRATION.md`](./COHERE_INTEGRATION.md) | Contexto: beneficios, riesgos y consideraciones de usar Cohere. |
| [`COHERE_RERANK_STEP_BY_STEP.md`](./COHERE_RERANK_STEP_BY_STEP.md) | Pasos normativos para **implementar** el rerank. |
| **Este archivo** | Resumen del contenido por sección del paso a paso. |

---

## Mapa sección por sección

### Encabezado (antes de la sección 0)

Define **audiencia** (agentes/IA), **objetivo técnico** (postprocesador LlamaIndex entre Supabase y Gemini) y el criterio de **idioma** (identificadores en inglés estándar).

### Sección 0 — Contract for automated execution

Es el **contrato** de la tarea: qué archivos se pueden tocar, cuáles no, qué comportamiento debe mantenerse cuando el rerank está apagado y cuándo se considera **terminado** el trabajo. Evita que un agente modifique `worker.py` o rompa el modo sin Cohere.

### Sección 1 — Repository facts


Lista **hechos comprobables** del repo: funciones y rutas (`initialize_query_engine`, `/api/chat`), servicio Docker `fastapi_app`, y **cadenas de búsqueda** para localizar código sin depender de números de línea que cambian.

### Sección 2 — Environment variables

Especifica **todas** las variables nuevas (`COHERE_*`, `RERANK_TOP_N`, `VECTOR_RETRIEVAL_K`) y la **regla** de cuántos documentos recuperar según si el rerank está activo o no, más el **invariante** `retrieval_k >= RERANK_TOP_N`.

### Sección 3 — Dependency

Indica la línea exacta en `requirements.txt` y comandos para **verificar** que el paquete de LlamaIndex para Cohere se instala e importa.

### Sección 4 — New module `app/cohere_rerank.py`

Describe el módulo recomendado: funciones `is_rerank_active`, `build_cohere_rerank_postprocessors`, `effective_similarity_top_k`, política **fail-open** (si falla Cohere, el chat sigue sin rerank) e implementación de referencia en bloques de código.

### Sección 5 — Modify `app/main.py`

Instrucciones **obligatorias** para tocar **dos** sitios donde se llama `as_query_engine`: el arranque global y el chat por curso. Exige **la misma lógica** en ambos para no tener comportamientos distintos.

### Sección 6 — Docker

Comandos para **reconstruir** el servicio que ejecuta la API tras cambiar dependencias.

### Sección 7 — Verification checklist

Tabla **V1–V4**: pruebas mínimas (import, health, chat, fallo con clave inválida sin tumbar el servidor).

### Sección 8 — Rollback

Cómo **deshacer** la activación (variables, código opcional, dependencia).

### Sección 9 — Non-goals

Límites explícitos de alcance para que un agente no cambie SQL, privacidad por cuenta propia ni añada Cohere al worker de ingesta.

### Sección 10 — Human references

Enlaces externos (PyPI, documentación Cohere) para resolver dudas que el procedimiento no automatiza (por ejemplo, nombre exacto del modelo rerank).

---

## Cómo usar estos dos documentos juntos

1. **Lectura humana rápida:** este archivo (`..._EXPLAINED.md`) + [`COHERE_INTEGRATION.md`](./COHERE_INTEGRATION.md) para el “por qué” y riesgos.
2. **Implementación (persona o IA):** seguir [`COHERE_RERANK_STEP_BY_STEP.md`](./COHERE_RERANK_STEP_BY_STEP.md) de arriba abajo; usar la sección 0 como checklist de cierre.
3. **Soporte:** si algo falla, la sección 7 del paso a paso delimita qué verificar antes de cambiar diseño.

---

*Este resumen describe la estructura del paso a paso vigente en el repositorio; si el archivo principal cambia, conviene actualizar este mapa.*

