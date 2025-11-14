"""
API Backend del Chatbot Educativo
==================================

Esta API proporciona endpoints para interactuar con el chatbot educativo
que utiliza RAG (Retrieval-Augmented Generation) con Gemini y Supabase (pgvector).
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pathlib import Path
import httpx

from llama_index.core import VectorStoreIndex, Settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

from app.supabase_vector_store import SupabaseVectorStore

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variable global para el motor de consulta
query_engine = None


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class QueryRequest(BaseModel):
    """Modelo para las solicitudes de chat."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="La pregunta del usuario sobre el curso"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "¿Cuáles son los temas principales del módulo 1?"
            }
        }


class QueryResponse(BaseModel):
    """Modelo para las respuestas del chatbot."""
    answer: str = Field(..., description="La respuesta generada por el chatbot")
    sources: Optional[list] = Field(
        default=None,
        description="Fuentes utilizadas para generar la respuesta"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Los temas principales del módulo 1 son...",
                "sources": ["documento1.pdf", "documento2.pdf"]
            }
        }


class HealthResponse(BaseModel):
    """Modelo para la respuesta del health check."""
    status: str
    message: str
    model: str
    collection_count: Optional[int] = None


class ContentIngestPayload(BaseModel):
    """Modelo para el payload de ingesta de contenido."""
    unique_content_id: str = Field(..., description="ID único del contenido")
    course_slug: str = Field(..., description="Slug del curso")
    course_name: str = Field(..., description="Nombre del curso")
    topic_id: str = Field(..., description="ID del tópico")
    model: str = Field(..., description="Modelo del contenido")
    version: str = Field(..., description="Versión del contenido")
    title: str = Field(..., description="Título del contenido")
    module: str = Field(..., description="Módulo del contenido")
    notes: str = Field(..., description="Notas adicionales")
    version_data: str = Field(..., description="Datos de la versión")
    content: str = Field(..., min_length=1, description="Contenido principal a indexar")

    class Config:
        json_schema_extra = {
            "example": {
                "unique_content_id": "course_123_topic_456",
                "course_slug": "mantenimiento-mecanico",
                "course_name": "Mantenimiento Mecánico Automotriz",
                "topic_id": "topic_456",
                "model": "standard",
                "version": "1.0",
                "title": "Introducción al Mantenimiento",
                "module": "Módulo 1",
                "notes": "Versión inicial del contenido",
                "version_data": "2025-01-15",
                "content": "El mantenimiento mecánico automotriz es fundamental..."
            }
        }


class ContentIngestResponse(BaseModel):
    """Modelo para la respuesta de ingesta de contenido."""
    message: str
    job_id: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Content received and queued for processing.",
                "job_id": 123
            }
        }


# ============================================================================
# LIFECYCLE MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    # Startup
    logger.info("🚀 Iniciando la aplicación...")
    await initialize_query_engine()

    yield

    # Shutdown
    logger.info("👋 Cerrando la aplicación...")


# ============================================================================
# INICIALIZACIÓN
# ============================================================================

async def initialize_query_engine():
    """Inicializa el motor de consulta RAG."""
    global query_engine

    try:
        # 1. Validar API Key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("❌ GOOGLE_API_KEY no está configurada.")
            logger.error("Consulta SETUP_API_KEY.md para obtener instrucciones.")
            return

        # 2. Obtener configuración
        model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
        embedding_model = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        table_name = os.getenv("SUPABASE_TABLE_NAME", "documents")
        rpc_function = os.getenv("SUPABASE_RPC_FUNCTION", "match_ec1121_gemi_mantenimiento_mecanico_automotriz")
        embed_dim = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
        match_threshold = float(os.getenv("MATCH_THRESHOLD", "0.5"))
        similarity_top_k = int(os.getenv("SIMILARITY_TOP_K", "3"))
        logger.info(f"🔧 Working with function: {rpc_function}")

        if not supabase_url or not supabase_key:
            logger.error("❌ SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no están configuradas.")
            logger.error("Por favor, configura estas variables en .env")
            return

        logger.info("📝 Configuración:")
        logger.info(f"   - Modelo LLM: {model}")
        logger.info(f"   - Modelo de Embeddings: {embedding_model}")
        logger.info(f"   - Supabase URL: {supabase_url}")
        logger.info(f"   - Tabla: {table_name}")
        logger.info(f"   - RPC Function: {rpc_function}")
        logger.info(f"   - Dimensiones de embedding: {embed_dim}")
        logger.info(f"   - Match Threshold: {match_threshold}")
        logger.info(f"   - Top K: {similarity_top_k}")

        # 3. Configurar LlamaIndex
        Settings.llm = GoogleGenAI(model=model)
        Settings.embed_model = GoogleGenAIEmbedding(model_name=embedding_model)

        # 4. Conectar a Supabase usando API REST
        logger.info("🔌 Conectando a Supabase vía API REST...")

        vector_store = SupabaseVectorStore(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            table_name=table_name,
            rpc_function_name=rpc_function,
            embed_dim=embed_dim,
            match_threshold=match_threshold,
        )

        logger.info("✅ Conexión a Supabase exitosa.")

        # 5. Crear el índice vectorial
        logger.info("🔍 Creando el índice vectorial...")
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

        # 6. Crear el motor de consulta con instrucciones en español
        from llama_index.core.prompts import PromptTemplate

        # Template de sistema en español
        qa_prompt_template = PromptTemplate(
            "Eres un asistente educativo experto en mantenimiento mecánico automotriz. "
            "Tu objetivo es ayudar a estudiantes a aprender sobre este tema.\n\n"
            "IMPORTANTE: Siempre responde en español, sin importar el idioma de la pregunta.\n\n"
            "Contexto de referencia:\n"
            "{context_str}\n\n"
            "Pregunta: {query_str}\n\n"
            "Instrucciones:\n"
            "1. Responde ÚNICAMENTE en español\n"
            "2. Usa el contexto proporcionado para dar respuestas precisas\n"
            "3. Si no encuentras la respuesta en el contexto, indícalo claramente\n"
            "4. Sé claro, educativo y profesional\n\n"
            "Respuesta en español:"
        )

        query_engine = index.as_query_engine(
            streaming=False,
            similarity_top_k=similarity_top_k,
            text_qa_template=qa_prompt_template,
        )

        logger.info("✅ Motor de consulta inicializado correctamente.")

    except Exception as e:
        logger.error(f"❌ Error al inicializar el motor de consulta: {e}")
        logger.error("Detalles del error:", exc_info=True)
        query_engine = None


# ============================================================================
# APLICACIÓN FASTAPI
# ============================================================================

app = FastAPI(
    title="Chatbot Educativo API",
    description="""
    API para interactuar con un chatbot educativo que utiliza
    Retrieval-Augmented Generation (RAG) con Gemini y Supabase (pgvector).

    ## Características

    * 🤖 Respuestas basadas en el contenido del curso
    * 🔍 Búsqueda semántica en documentos con pgvector
    * 🚀 Powered by Google Gemini
    * 📚 Base de conocimiento en Supabase

    ## Uso

    1. Configura la conexión a Supabase en .env
    2. Envía preguntas a `/api/chat`
    3. Recibe respuestas fundamentadas en los materiales del curso
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos del frontend
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    logger.info(f"✅ Frontend montado en /static desde {frontend_path}")
else:
    logger.warning(f"⚠️  No se encontró el directorio frontend en {frontend_path}")


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """
    Endpoint raíz - Sirve la interfaz web del chatbot.

    Si el frontend está disponible, retorna el index.html.
    De lo contrario, retorna información de la API.
    """
    frontend_index = frontend_path / "index.html"

    if frontend_index.exists():
        return FileResponse(str(frontend_index))
    else:
        return {
            "message": "API del Chatbot Educativo está en funcionamiento.",
            "version": "1.0.0",
            "endpoints": {
                "chat": "/api/chat",
                "health": "/health",
                "docs": "/docs"
            },
            "note": "Frontend no disponible. Para probar la API, visita /docs"
        }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Endpoint de health check.

    Verifica el estado de la aplicación y la conexión con Supabase.
    """
    if query_engine is None:
        return HealthResponse(
            status="unhealthy",
            message="El motor de consulta no está disponible. Verifica los logs.",
            model=os.getenv("GEMINI_MODEL", "unknown")
        )

    try:
        return HealthResponse(
            status="healthy",
            message="Todos los sistemas operativos. Conectado a Supabase.",
            model=os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest"),
            collection_count=None
        )

    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return HealthResponse(
            status="degraded",
            message=f"Error al verificar el estado: {str(e)}",
            model=os.getenv("GEMINI_MODEL", "unknown")
        )


@app.post("/api/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest):
    """
    Endpoint principal del chatbot.

    Recibe una pregunta del usuario y devuelve una respuesta
    generada usando RAG (Retrieval-Augmented Generation).

    **Parámetros:**
    - `question`: La pregunta del usuario sobre el contenido del curso

    **Retorna:**
    - `answer`: La respuesta generada por el chatbot
    - `sources`: Lista de fuentes utilizadas (opcional)
    """
    if query_engine is None:
        raise HTTPException(
            status_code=503,
            detail="El motor de consulta no está disponible. Verifica los logs del servidor."
        )

    logger.info(f"📩 Pregunta recibida: {request.question}")

    try:
        # Realizar la consulta
        logger.info(f"🔍 Iniciando búsqueda vectorial y generación de respuesta...")
        response = query_engine.query(request.question)
        logger.info(f"✅ Query ejecutado exitosamente")

        # Extraer la respuesta
        answer = str(response)

        # Extraer fuentes si están disponibles
        sources = []
        source_count = 0
        if hasattr(response, 'source_nodes'):
            source_count = len(response.source_nodes)
            logger.info(f"📚 Source nodes encontrados: {source_count}")

            for node in response.source_nodes:
                if hasattr(node, 'node') and hasattr(node.node, 'metadata'):
                    metadata = node.node.metadata
                    if 'file_name' in metadata:
                        sources.append(metadata['file_name'])

        # Eliminar duplicados de fuentes
        sources = list(set(sources)) if sources else None

        # Validar si la base de datos está vacía
        if source_count == 0:
            logger.warning(f"⚠️  Base de datos vacía: No se encontraron documentos relevantes")
            logger.warning(f"   La respuesta de Gemini puede ser generada sin contexto del curso")
            # Agregar nota a la respuesta para el usuario
            answer = (
                f"{answer}\n\n"
                "**Nota**: La base de conocimiento está actualmente vacía. "
                "Esta respuesta fue generada sin contexto específico del curso."
            )

        logger.info(f"✅ Respuesta generada exitosamente.")
        if sources:
            logger.info(f"📚 Fuentes utilizadas: {sources}")
        else:
            logger.info(f"📚 Sin fuentes disponibles (base de datos vacía)")

        return QueryResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"❌ Error al procesar la consulta: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar la pregunta: {str(e)}"
        )


@app.post("/api/v1/ingest", response_model=ContentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_content(payload: ContentIngestPayload):
    """
    Endpoint para ingesta asíncrona de contenido.

    Recibe contenido desde un sistema externo y lo encola para procesamiento.
    El contenido será indexado de forma asíncrona por un worker en background.

    **Comportamiento:**
    - Valida el payload recibido
    - Crea un job en la cola de ingesta
    - Retorna inmediatamente con 202 Accepted
    - El worker procesará el job de forma asíncrona:
      1. Eliminará el contenido antiguo con el mismo unique_content_id
      2. Indexará el nuevo contenido
      3. Actualizará el estado del job

    **Parámetros:**
    - `unique_content_id`: ID único para identificar y actualizar el contenido
    - `content`: Texto principal a indexar
    - `topic_id`, `version`, `title`: Metadata importante para filtrado
    - Otros campos: Metadata adicional almacenada con el contenido

    **Retorna:**
    - `message`: Confirmación de que el contenido fue encolado
    - `job_id`: ID del job creado para seguimiento
    """
    # Validar que el contenido no esté vacío
    if not payload.unique_content_id or not payload.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unique_content_id and content are required and cannot be empty."
        )

    # Obtener configuración de Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        logger.error("❌ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error. Please contact administrator."
        )

    try:
        # Crear el payload del job (convertir a dict)
        job_payload = payload.model_dump()

        # Preparar datos para insertar en la tabla de jobs
        job_data = {
            "status": "pending",
            "payload": job_payload
        }

        # Headers para autenticación con Supabase
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"  # Para obtener el ID del job insertado
        }

        # Insertar el job en la tabla usando httpx
        url = f"{supabase_url.rstrip('/')}/rest/v1/ingestion_jobs"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=job_data, headers=headers)
            response.raise_for_status()

            # Obtener el ID del job insertado
            result = response.json()
            job_id = result[0].get("id") if result and len(result) > 0 else None

            logger.info(
                f"✅ Content queued for ingestion. "
                f"Job ID: {job_id}, "
                f"unique_content_id: {payload.unique_content_id}"
            )

            return ContentIngestResponse(
                message="Content received and queued for processing.",
                job_id=job_id
            )

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP error queuing ingestion job: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue content for processing. Please try again."
        )
    except Exception as e:
        logger.error(f"❌ Error queuing ingestion job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue content for processing."
        )


# ============================================================================
# DESARROLLO Y TESTING
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
