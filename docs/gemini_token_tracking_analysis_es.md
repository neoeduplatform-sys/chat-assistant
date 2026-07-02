# Seguimiento de Tokens y Análisis de Costos de Gemini

Este documento proporciona un análisis exhaustivo de cómo podemos extraer, rastrear y calcular el uso de tokens y los costos para cada solicitud de cliente al comunicarse con la API de Google Gemini utilizando LlamaIndex.

## 1. Disponibilidad de Datos de Uso de Tokens en la API

Sí, la información de uso de tokens está completamente disponible cuando se utiliza la clase `GoogleGenAI` de LlamaIndex (que envuelve la API de Gemini).

### Cómo Expone LlamaIndex los Conteos de Tokens
Para cada respuesta de LLM (`ChatResponse` o `CompletionResponse`), la integración `llama-index-llms-google-genai` mapea automáticamente los metadatos de uso (`usage_metadata`) de la API de Gemini en dos lugares del objeto devuelto:

1. **`response.additional_kwargs`**:
   LlamaIndex mapea las estadísticas de uso en claves de diccionario estándar:
   - `prompt_tokens`: Número de tokens de entrada en la solicitud (prompt).
   - `completion_tokens`: Número de tokens de salida generados por Gemini.
   - `total_tokens`: Tokens totales (`prompt_tokens` + `completion_tokens`).

2. **`response.raw`**:
   El objeto de respuesta sin procesar devuelto por el SDK de Google GenAI se conserva aquí. Contiene un objeto `usage_metadata` con los campos:
   - `prompt_token_count`
   - `candidates_token_count`
   - `total_token_count`

---

## 2. Seguimiento Dinámico de Tokens por Solicitud

Dado que el backend está construido sobre **FastAPI** y procesa múltiples solicitudes de forma concurrente, debemos realizar el seguimiento del uso de tokens de manera segura para hilos (thread-safe) y evitar condiciones de carrera (race conditions).

Dentro de un único ciclo de solicitud, existen dos llamadas de LLM distintas:
1. **Síntesis de Respuesta RAG**: Generar la respuesta principal a través de `course_query_engine.synthesize(...)`.
2. **Resumen de Memoria Flotante** (Opcional): Actualizar el resumen de la conversación a través de `summarize_conversation(...)` si el límite de tokens del resumen activa una actualización.

### La Solución con Callback y ContextVars
Para capturar de forma dinámica los tokens de **ambas** llamadas y asociarlos con la solicitud HTTP actual, podemos utilizar un `CallbackHandler` personalizado de LlamaIndex combinado con el módulo integrado `contextvars` de Python.

```python
import contextvars
import logging
from typing import Any, Dict, Optional
from llama_index.core.callbacks import BaseCallbackHandler, CBEventType, EventPayload

logger = logging.getLogger(__name__)

# Diccionario local al contexto para rastrear tokens durante una solicitud HTTP activa
token_tracker_context = contextvars.ContextVar("token_tracker_context", default=None)

class TokenTrackerCallbackHandler(BaseCallbackHandler):
    """Callback Handler personalizado de LlamaIndex para rastrear conteos de tokens de LLM de forma segura para hilos."""
    
    def __init__(self) -> None:
        super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])

    def on_event_start(self, event_type, payload=None, event_id="", parent_id="", **kwargs):
        return event_id

    def on_event_end(self, event_type, payload=None, event_id="", **kwargs):
        if event_type == CBEventType.LLM and payload:
            response = payload.get(EventPayload.RESPONSE)
            if response:
                additional_kwargs = getattr(response, "additional_kwargs", {}) or {}
                p_tokens = additional_kwargs.get("prompt_tokens")
                c_tokens = additional_kwargs.get("completion_tokens")
                
                # Alternativa (fallback) a la respuesta sin procesar si faltan las claves en additional_kwargs
                raw_response = getattr(response, "raw", None)
                if raw_response and (p_tokens is None or c_tokens is None):
                    usage_metadata = getattr(raw_response, "usage_metadata", None)
                    if usage_metadata:
                        p_tokens = getattr(usage_metadata, "prompt_token_count", p_tokens)
                        c_tokens = getattr(usage_metadata, "candidates_token_count", c_tokens)
                
                # Actualizar el rastreador local al contexto si está activo
                tracker = token_tracker_context.get()
                if tracker is not None:
                    if p_tokens is not None:
                        tracker["prompt_tokens"] += int(p_tokens)
                    if c_tokens is not None:
                        tracker["completion_tokens"] += int(c_tokens)
                    tracker["total_tokens"] = tracker["prompt_tokens"] + tracker["completion_tokens"]
```

---

## 3. Cálculo de Costos por Solicitud

El costo se puede calcular dinámicamente al final del manejador de la solicitud comparando el nombre del modelo con las tablas de precios vigentes.

### Modelo de Precios de la API de Gemini (USD por Millón de Tokens)

| Nombre del Modelo | Tarifa de Entrada (por 1M de tokens) | Tarifa de Salida (por 1M de tokens) |
| :--- | :--- | :--- |
| **Gemini 1.5 Pro** | $1.25 | $5.00 |
| **Gemini 2.5 Flash** | $0.30 | $2.50 |
| **Gemini 1.5 Flash** | $0.075 | $0.30 |

### Utilidad de Cálculo de Costos
```python
def calculate_gemini_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calcular el costo de la solicitud en USD según los precios del modelo."""
    model = (model_name or "").lower()
    
    # Tarifas predeterminadas (Gemini 1.5 Pro)
    input_rate = 1.25 / 1_000_000
    output_rate = 5.00 / 1_000_000
    
    if "gemini-2.5-flash" in model:
        input_rate = 0.30 / 1_000_000
        output_rate = 2.50 / 1_000_000
    elif "gemini-1.5-flash" in model:
        input_rate = 0.075 / 1_000_000
        output_rate = 0.30 / 1_000_000
    elif "gemini-1.5-pro" in model:
        input_rate = 1.25 / 1_000_000
        output_rate = 5.00 / 1_000_000
        
    return (prompt_tokens * input_rate) + (completion_tokens * output_rate)
```

---

## 4. Pasos de Implementación (Modificaciones Planificadas)

Una vez aprobado, el mecanismo de seguimiento se integrará en la base de código de la siguiente manera:

### Paso 1: Actualizar los Modelos de Respuesta de la API (`app/models.py`)
Introducir un modelo `TokenUsageInfo` y agregarlo como un campo opcional en `ChatResponse`:
```python
class TokenUsageInfo(BaseModel):
    prompt_tokens: int = Field(..., description="Number of input tokens")
    completion_tokens: int = Field(..., description="Number of output tokens")
    total_tokens: int = Field(..., description="Total tokens used")
    cost: float = Field(..., description="Cost of the request in USD")

class ChatResponse(BaseModel):
    # Campos existentes...
    answer: str
    sources: Optional[List[str]] = None
    course_id: str
    user_id: Optional[str] = None
    # Nuevos metadatos de seguimiento
    usage: Optional[TokenUsageInfo] = Field(None, description="Token usage and cost metrics")
```

### Paso 2: Registrar el Callback Handler global (`app/main.py`)
En `initialize_query_engine()` durante la inicialización de LlamaIndex:
```python
        # Registrar el callback handler de seguimiento de tokens globalmente
        from llama_index.core.callbacks import CallbackManager
        Settings.callback_manager = CallbackManager([TokenTrackerCallbackHandler()])
```

### Paso 3: Implementar la Gestión del Contexto en el Endpoint de Chat (`app/main.py`)
Envolver el procesamiento de `/api/chat` en un contexto `try...finally` para establecer, actualizar y leer el `token_tracker_context`:
```python
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user = Depends(get_current_user)):
    ...
    # 1. Inicializar el rastreador en el contexto actual
    token = token_tracker_context.set({
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    })
    
    try:
        # Proceder con la ejecución del motor de consulta existente y el resumen
        ...
        
        # 2. Extraer el uso acumulado de tokens
        usage_data = token_tracker_context.get()
        model_name = getattr(Settings.llm, "model", None) or os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
        
        cost = calculate_gemini_cost(model_name, usage_data["prompt_tokens"], usage_data["completion_tokens"])
        
        # 3. Registrar los resultados en el registro del sistema (log)
        logger.info(
            "📊 Request Token Usage | model=%s | prompt=%d | completion=%d | total=%d | cost=$%.6f",
            model_name, usage_data["prompt_tokens"], usage_data["completion_tokens"], usage_data["total_tokens"], cost
        )
        
        # 4. Devolver la respuesta enriquecida
        return ChatResponse(
            answer=answer,
            sources=sources,
            course_id=request.course_id,
            user_id=request.user_id,
            usage=TokenUsageInfo(
                prompt_tokens=usage_data["prompt_tokens"],
                completion_tokens=usage_data["completion_tokens"],
                total_tokens=usage_data["total_tokens"],
                cost=cost
            )
        )
    finally:
        # 5. Limpiar la ContextVar para evitar fugas de memoria
        token_tracker_context.reset(token)
```
