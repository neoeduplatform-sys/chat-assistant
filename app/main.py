"""
API Backend del Chatbot Educativo
==================================

Esta API proporciona endpoints para interactuar con el chatbot educativo
que utiliza RAG (Retrieval-Augmented Generation) con Gemini y Supabase (pgvector).
"""

import os
import logging
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from pathlib import Path
import httpx

from llama_index.core import VectorStoreIndex, Settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

from app.supabase_vector_store import SupabaseVectorStore
from app.course_config import get_course_config_service
from app.models import (
    ChatRequest,
    ChatResponse,
    CourseConfigCreate,
    CourseConfigUpdate,
    CourseConfigResponse,
    CourseConfigList,
    ErrorResponse
)

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
    course_id: str = Field(..., description="ID único del curso")
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
                "course_id": "mantenimiento-mecanico",
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint principal del chatbot con soporte multi-curso.

    Recibe una pregunta del usuario con el ID del curso y devuelve una respuesta
    generada usando RAG (Retrieval-Augmented Generation) con el contexto del curso específico.

    **Parámetros:**
    - `question`: La pregunta del usuario sobre el contenido del curso
    - `course_id`: ID del curso (requerido)
    - `user_id`: ID del usuario (opcional, para tracking)

    **Retorna:**
    - `answer`: La respuesta generada por el chatbot
    - `sources`: Lista de fuentes utilizadas (opcional)
    - `course_id`: ID del curso usado
    - `user_id`: ID del usuario (si se proporcionó)
    """
    logger.info(f"📩 Pregunta recibida: {request.question} | Course: {request.course_id}")

    try:
        # 1. Obtener configuración del curso
        course_service = get_course_config_service()
        course_config = course_service.get_course_config(request.course_id, use_cache=True)

        if not course_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{request.course_id}' not found or inactive."
            )

        logger.info(f"✅ Course config retrieved: {course_config['course_name']}")
        logger.info(f"   Table: {course_config['table_name']}")
        logger.info(f"   RPC: {course_config['rpc_function']}")

        # 2. Crear vector store dinámico para este curso
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        embed_dim = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
        match_threshold = float(os.getenv("MATCH_THRESHOLD", "0.5"))
        similarity_top_k = int(os.getenv("SIMILARITY_TOP_K", "3"))

        vector_store = SupabaseVectorStore(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            table_name=course_config['table_name'],
            rpc_function_name=course_config['rpc_function'],
            embed_dim=embed_dim,
            match_threshold=match_threshold,
        )

        # 3. Crear índice vectorial dinámico
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

        # 4. Crear query engine con prompt personalizado
        from llama_index.core.prompts import PromptTemplate

        qa_prompt_template = PromptTemplate(
            f"Eres un asistente educativo experto en {course_config['course_name']}. "
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

        course_query_engine = index.as_query_engine(
            streaming=False,
            similarity_top_k=similarity_top_k,
            text_qa_template=qa_prompt_template,
        )

        # 5. Realizar la consulta
        logger.info(f"🔍 Iniciando búsqueda vectorial y generación de respuesta...")
        response = course_query_engine.query(request.question)
        logger.info(f"✅ Query ejecutado exitosamente")

        # 6. Extraer la respuesta
        answer = str(response)

        # 7. Extraer fuentes si están disponibles
        sources = []
        source_count = 0
        if hasattr(response, 'source_nodes'):
            source_count = len(response.source_nodes)
            logger.info(f"📚 Source nodes encontrados: {source_count}")

            for node in response.source_nodes:
                if hasattr(node, 'node') and hasattr(node.node, 'metadata'):
                    metadata = node.node.metadata
                    # Extraer título o unique_content_id como fuente
                    source = metadata.get('title') or metadata.get('unique_content_id') or metadata.get('file_name')
                    if source:
                        sources.append(source)

        # Eliminar duplicados de fuentes
        sources = list(set(sources)) if sources else None

        # 8. Validar si la base de datos está vacía
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

        return ChatResponse(
            answer=answer,
            sources=sources,
            course_id=request.course_id,
            user_id=request.user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error al procesar la consulta: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
    - Valida que el curso existe y está activo
    - Crea un job en la cola de ingesta
    - Retorna inmediatamente con 202 Accepted
    - El worker procesará el job de forma asíncrona:
      1. Eliminará el contenido antiguo con el mismo unique_content_id
      2. Indexará el nuevo contenido
      3. Actualizará el estado del job

    **Parámetros:**
    - `unique_content_id`: ID único para identificar y actualizar el contenido
    - `course_id`: ID del curso (debe existir en course_configurations)
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

    # Validar que el curso existe
    try:
        course_service = get_course_config_service()
        course_config = course_service.get_course_config(payload.course_id, use_cache=True)

        if not course_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{payload.course_id}' not found or inactive. "
                       f"Please create the course configuration first via POST /api/v1/courses"
            )

        logger.info(f"✅ Course validated for ingestion: {course_config['course_name']}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error validating course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating course configuration."
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
# COURSE MANAGEMENT ENDPOINTS
# ============================================================================

@app.get(
    "/api/v1/courses",
    response_model=CourseConfigList,
    tags=["Course Management"],
    summary="List all course configurations"
)
async def list_courses(active_only: bool = True):
    """
    List all course configurations.

    **Parameters:**
    - `active_only`: If true, only return active courses (default: true)

    **Returns:**
    - List of course configurations with metadata
    """
    try:
        course_service = get_course_config_service()
        courses = course_service.list_course_configs(active_only=active_only)

        return CourseConfigList(
            courses=[CourseConfigResponse(**course) for course in courses],
            total=len(courses)
        )

    except Exception as e:
        logger.error(f"❌ Error listing courses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course list."
        )


@app.get(
    "/api/v1/courses/{course_id}",
    response_model=CourseConfigResponse,
    tags=["Course Management"],
    summary="Get specific course configuration"
)
async def get_course(course_id: str):
    """
    Get a specific course configuration by ID.

    **Parameters:**
    - `course_id`: The unique course identifier

    **Returns:**
    - Course configuration details
    """
    try:
        course_service = get_course_config_service()
        course = course_service.get_course_config(course_id, use_cache=True)

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{course_id}' not found or inactive."
            )

        return CourseConfigResponse(**course)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving course {course_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course configuration."
        )


@app.post(
    "/api/v1/courses",
    response_model=CourseConfigResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Course Management"],
    summary="Create new course configuration"
)
async def create_course(course_data: CourseConfigCreate):
    """
    Create a new course configuration.

    **Parameters:**
    - `course_data`: Course configuration details including:
      - `course_id`: Unique identifier (required)
      - `course_name`: Human-readable name
      - `course_slug`: URL-friendly slug
      - `table_name`: Supabase table name for vectors
      - `rpc_function`: Supabase RPC function for search
      - `active`: Whether the course is active (default: true)
      - `description`: Optional description
      - `metadata`: Optional additional metadata

    **Returns:**
    - Created course configuration

    **Note:**
    - The course_id must be unique
    - Make sure the corresponding Supabase table and RPC function exist
    """
    try:
        course_service = get_course_config_service()
        created_course = course_service.create_course_config(course_data.model_dump())

        logger.info(f"✅ Course created: {course_data.course_id}")
        return CourseConfigResponse(**created_course)

    except ValueError as e:
        # Course ID already exists
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Error creating course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create course configuration."
        )


@app.put(
    "/api/v1/courses/{course_id}",
    response_model=CourseConfigResponse,
    tags=["Course Management"],
    summary="Update course configuration"
)
async def update_course(course_id: str, update_data: CourseConfigUpdate):
    """
    Update an existing course configuration.

    **Parameters:**
    - `course_id`: The course identifier
    - `update_data`: Fields to update (all optional)

    **Returns:**
    - Updated course configuration
    """
    try:
        course_service = get_course_config_service()

        # Filter out None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update."
            )

        updated_course = course_service.update_course_config(course_id, update_dict)

        if not updated_course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{course_id}' not found."
            )

        logger.info(f"✅ Course updated: {course_id}")
        return CourseConfigResponse(**updated_course)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating course {course_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update course configuration."
        )


@app.delete(
    "/api/v1/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Course Management"],
    summary="Delete/deactivate course configuration"
)
async def delete_course(course_id: str, hard_delete: bool = False):
    """
    Delete or deactivate a course configuration.

    **Parameters:**
    - `course_id`: The course identifier
    - `hard_delete`: If true, permanently delete; if false, just deactivate (default: false)

    **Returns:**
    - 204 No Content on success

    **Note:**
    - Soft delete (default) sets active=false, preserving the record
    - Hard delete permanently removes the record from the database
    - Soft delete is recommended to maintain data integrity
    """
    try:
        course_service = get_course_config_service()
        success = course_service.delete_course_config(course_id, soft_delete=not hard_delete)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{course_id}' not found."
            )

        action = "deactivated" if not hard_delete else "deleted"
        logger.info(f"✅ Course {action}: {course_id}")
        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting course {course_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete course configuration."
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
