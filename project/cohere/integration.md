# Integración de Cohere (reranker) en el chatbot RAG

Este documento resume **beneficios**, **riesgos** y **consideraciones** al integrar **Cohere** principalmente como **modelo de reranking** sobre los resultados ya recuperados por búsqueda vectorial (Supabase / pgvector). No sustituye la lectura de la documentación oficial de Cohere ni la evaluación legal/privacidad en tu organización.

---

## Contexto en este proyecto

- **Recuperación actual:** embeddings (p. ej. Gemini) + función RPC en Supabase + umbral (`MATCH_THRESHOLD`) y `SIMILARITY_TOP_K`.
- **Rol de Cohere como reranker:** reordenar (y recortar a `top_n`) los fragmentos ya devueltos por el vector store, para que el contexto enviado al LLM sea más alineado con la pregunta del usuario.

---

## Beneficios

1. **Mejor relevancia del contexto**  
   La similitud vectorial mide “cercanía” en el espacio de embeddings; no siempre coincide con “este párrafo responde a la pregunta”. Un reranker entrenado para relevancia puede **subir** fragmentos útiles y **bajar** ruido semánticamente cercano pero inútil.

2. **Desacoplar “traer candidatos” de “elegir los mejores”**  
   Puedes subir el número de candidatos recuperados (`similarity_top_k`) y dejar que el rerank deje solo los **N** mejores para el prompt. Eso ayuda cuando el umbral vectorial es un compromiso entre “no devuelve nada” y “devuelve basura”.

3. **Sin reindexar la base vectorial**  
   Integrar solo rerank **no exige** cambiar modelo de embeddings ni dimensiones en Supabase ni reingestar documentos (a diferencia de cambiar solo a embeddings de Cohere).

4. **Cambio acotado en la arquitectura**  
   En stacks con LlamaIndex suele añadirse un **postprocesador** (`node_postprocessors`) al `query_engine`, sin reescribir todo el flujo RAG.

5. **Ajuste fino con pocos hiperparámetros**  
   Sobre todo `top_n` del rerank y cuántos candidatos pides al retriever; iteración más simple que migrar de proveedor de embeddings.

---

## Riesgos

1. **Latencia**  
   Cada consulta añade al menos una llamada HTTP a Cohere tras el retrieval. El tiempo de respuesta percibido por el usuario aumenta.

2. **Coste recurrente**  
   Rerank suele facturarse por volumen (p. ej. tokens o peticiones). Tráfico alto implica coste además de Gemini y del propio alojamiento.

3. **Disponibilidad y dependencia externa**  

   El flujo depende de que la API de Cohere responda correctamente. Fallos, mantenimientos o límites de tasa pueden provocar errores o timeouts si no hay **reintentos** o **fallback** (continuar sin rerank).

4. **Privacidad y cumplimiento**  
   Pregunta y fragmentos de documentos se envían a infraestructura de Cohere. Deben revisarse términos de servicio, tratamiento de datos, ubicación/región y requisitos contractuales (p. ej. entorno educativo, datos personales).

5. **No arregla un retrieval fundamentalmente roto**  
   Si la búsqueda vectorial devuelve pocos o malos candidatos (tabla equivocada, umbral mal calibrado, chunks mal partidos, desajuste ingestión/consulta), el rerank **solo reordena** lo recibido; no inventa contexto adecuado.


6. **Idioma y dominio**  
   Conviene validar con contenido real en **español** y vocabulario del curso. En algunos dominios muy técnicos el beneficio puede ser menor o requerir más candidatos o otro modelo según la oferta de Cohere.

7. **Complejidad operativa**  
   Más variables de entorno, claves y posibles versiones de API/modelo; más superficie para errores de configuración en despliegue (Docker, `.env`).

---

## Consideraciones prácticas

### Diseño del pipeline

- Separar conceptualmente:
  - **`VECTOR_RETRIEVAL_K` (o equivalente):** cuántos nodos pide el retriever a Supabase (suele ser mayor).
  - **`RERANK_TOP_N`:** cuántos fragmentos pasan al LLM tras Cohere (suele ser menor, p. ej. 3–5).
- Si solo se usa un único `SIMILARITY_TOP_K` bajo, el rerank **no puede mejorar** lo que nunca se recuperó.

### Umbrales vectoriales

- Si el problema es “no trae nada”, a veces hay que **bajar** `MATCH_THRESHOLD` para alimentar al rerank con más candidatos (aceptando más ruido a la entrada, que el rerank intenta filtrar por orden).
- Si el problema es mucho ruido, combinar umbral razonable con **más candidatos + rerank** suele ser más estable que subir agresivamente el umbral sin más datos.

### Implementación típica (LlamaIndex)

- Paquete habitual: `llama-index-postprocessor-cohere-rerank` (ver documentación actual de LlamaIndex y PyPI).
- Variable de entorno: `COHERE_API_KEY` (nunca commitear).
- Registrar el postprocesador en `as_query_engine(..., node_postprocessors=[...])`.

### Mitigación de riesgos

- **Timeout** en la llamada a Cohere y **fallback:** si falla el rerank, usar el orden por similitud original.
- **Límite de tamaño** de textos enviados al rerank para controlar latencia y coste.
- **Logs:** número de resultados post–vector search y post–rerank para depurar.
- **Monitorización** de tasas de error y latencia p95/p99.

### Evaluación

- Probar con un conjunto fijo de preguntas representativas (incluidos casos que hoy fallan).
- Comparar calidad percibida, latencia y coste estimado antes de activar en producción para todos los usuarios.

---


## Referencias externas

- [Cohere](https://cohere.com) — producto, precios y políticas actualizadas.
- [Documentación Cohere](https://docs.cohere.com) — API de rerank y modelos disponibles.
- Documentación LlamaIndex sobre postprocesadores Cohere Rerank (buscar en el sitio oficial de LlamaIndex).

---


*Documento orientado al proyecto chat-assistant (FastAPI, LlamaIndex, Supabase, Gemini). Actualizar si cambia el stack o las integraciones.*

