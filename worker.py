"""
Ingestion Worker - Background Content Processor
================================================

Este worker procesa de forma asíncrona los jobs de ingesta de contenido.

Funcionamiento:
1. Polling: Consulta la tabla ingestion_jobs cada 10 segundos
2. Dequeue: Usa la función RPC dequeue_ingestion_job() para obtener un job de forma atómica
3. Process: Por cada job:
   - Elimina chunks antiguos con el mismo unique_content_id
   - Indexa el nuevo contenido usando LlamaIndex
   - Actualiza el estado del job (completed/failed)
4. Loop: Repite continuamente

El worker está diseñado para correr como un servicio de larga duración.
"""

import os
import sys
import logging
import time
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import httpx

from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.core.node_parser import SentenceSplitter

# Importar el vector store personalizado y course config service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.supabase_vector_store import SupabaseVectorStore
from app.course_config import get_course_config_service

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

def validate_environment() -> None:
    """Valida que todas las variables de entorno necesarias estén configuradas."""
    required_vars = [
        "GOOGLE_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        # Note: SUPABASE_TABLE_NAME is no longer required as it's now dynamic per course
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
        logger.error("Por favor, configura estas variables en el archivo .env")
        sys.exit(1)

    logger.info("✅ Todas las variables de entorno están configuradas")


def configure_llama_index() -> None:
    """Configura LlamaIndex con los modelos de Google Gemini."""
    # Obtener configuración
    model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
    embedding_model = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "20"))

    logger.info("📝 Configuración de LlamaIndex:")
    logger.info(f"   - Modelo LLM: {model}")
    logger.info(f"   - Modelo de Embeddings: {embedding_model}")
    logger.info(f"   - Chunk Size: {chunk_size}")
    logger.info(f"   - Chunk Overlap: {chunk_overlap}")

    # Configurar Settings globales de LlamaIndex
    Settings.llm = GoogleGenAI(model=model)
    Settings.embed_model = GoogleGenAIEmbedding(model_name=embedding_model)
    Settings.node_parser = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    logger.info("✅ LlamaIndex configurado correctamente")


def create_vector_store_for_course(course_id: str) -> SupabaseVectorStore:
    """
    Crea una instancia de vector store dinámica basada en la configuración del curso.

    Args:
        course_id: ID del curso (course_slug)

    Returns:
        SupabaseVectorStore configurado para el curso específico

    Raises:
        ValueError: Si el curso no existe o no está configurado
    """
    try:
        # Obtener configuración del curso
        course_service = get_course_config_service()
        course_config = course_service.get_course_config(course_id, use_cache=True)

        if not course_config:
            raise ValueError(f"Course '{course_id}' not found or inactive")

        # Configuración de Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        embed_dim = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
        match_threshold = float(os.getenv("MATCH_THRESHOLD", "0.5"))

        logger.info(f"🔌 Conectando a Supabase para curso: {course_config['course_name']}")
        logger.info(f"   - URL: {supabase_url}")
        logger.info(f"   - Tabla: {course_config['table_name']}")
        logger.info(f"   - Función RPC: {course_config['rpc_function']}")

        vector_store = SupabaseVectorStore(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            table_name=course_config['table_name'],
            rpc_function_name=course_config['rpc_function'],
            embed_dim=embed_dim,
            match_threshold=match_threshold,
        )

        logger.info(f"✅ Vector store creado para curso: {course_id}")
        return vector_store

    except Exception as e:
        logger.error(f"❌ Error creando vector store para curso {course_id}: {e}")
        raise


# ============================================================================
# PROCESAMIENTO DE JOBS
# ============================================================================

def process_job(job: Dict[str, Any]) -> tuple[str, Optional[str]]:
    """
    Procesa un job de ingesta con configuración dinámica de curso.

    Args:
        job: Diccionario con los datos del job (id, payload, etc.)

    Returns:
        Tupla (status, error_message)
        - status: 'completed' o 'failed'
        - error_message: Mensaje de error si falló, None si tuvo éxito
    """
    job_id = job['id']
    payload = job['payload']
    unique_id = payload.get('unique_content_id')
    content = payload.get('content')
    course_id = payload.get('course_id')

    if not unique_id or not content:
        logger.error(f"❌ Job {job_id} tiene payload inválido: falta unique_content_id o content")
        return "failed", "Missing unique_content_id or content in payload"

    if not course_id:
        logger.error(f"❌ Job {job_id} tiene payload inválido: falta course_id")
        return "failed", "Missing course_id in payload"

    try:
        logger.info(f"🚀 Procesando job {job_id} para unique_content_id: {unique_id}")
        logger.info(f"   Curso: {course_id}")

        # === 0. SETUP: Crear vector store dinámico para el curso ===
        try:
            vector_store = create_vector_store_for_course(course_id)
        except ValueError as e:
            logger.error(f"❌ Error: {e}")
            return "failed", str(e)
        except Exception as e:
            logger.error(f"❌ Error creando vector store: {e}")
            return "failed", f"Failed to create vector store: {str(e)}"

        # === 1. DELETE: Eliminar contenido antiguo ===
        # Eliminar todos los chunks existentes con este unique_content_id
        logger.info(f"🗑️  Eliminando contenido antiguo para {unique_id}...")
        deleted_count = vector_store.delete_by_metadata("unique_content_id", unique_id)
        logger.info(f"✅ {deleted_count} chunk(s) antiguo(s) eliminado(s)")

        # === 2. PREPARE: Crear documento con metadata ===
        # Preparar metadata con los campos importantes
        metadata = {
            "unique_content_id": unique_id,
            "course_id": payload.get("course_id", ""),
            "course_name": payload.get("course_name", ""),
            "topic_id": payload.get("topic_id", ""),
            "model": payload.get("model", ""),
            "version": payload.get("version", ""),
            "title": payload.get("title", ""),
            "module": payload.get("module", ""),
            "notes": payload.get("notes", ""),
            "version_data": payload.get("version_data", ""),
            # Agregar timestamp de ingesta
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Crear documento de LlamaIndex
        doc = Document(
            text=content,
            metadata=metadata,
        )

        logger.info(f"📄 Documento creado con {len(content)} caracteres")

        # === 3. INDEX: Indexar el nuevo contenido ===
        logger.info(f"🔍 Indexando nuevo contenido...")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Crear índice y agregar documento
        # Esto automáticamente:
        # - Divide el documento en chunks
        # - Genera embeddings para cada chunk
        # - Almacena en Supabase
        VectorStoreIndex.from_documents(
            [doc],
            storage_context=storage_context,
            show_progress=True
        )

        logger.info(f"✅ Contenido indexado exitosamente para {unique_id}")
        logger.info(f"📊 Metadata almacenada: topic_id={metadata['topic_id']}, version={metadata['version']}, title={metadata['title']}")

        return "completed", None

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error procesando job {job_id}: {error_msg}", exc_info=True)
        return "failed", error_msg


# ============================================================================
# WORKER LOOP
# ============================================================================

def dequeue_job(supabase_url: str, supabase_key: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el siguiente job pendiente de forma atómica usando la función RPC.

    Returns:
        Diccionario con los datos del job, o None si no hay jobs disponibles
    """
    url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/dequeue_ingestion_job"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # La función RPC retorna un array con un job, o un array vacío
            if data and len(data) > 0:
                return data[0]
            else:
                return None

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Error HTTP al obtener job: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"❌ Error al obtener job: {e}")
        return None


def update_job_status(
    job_id: int,
    status: str,
    error_message: Optional[str],
    supabase_url: str,
    supabase_key: str
) -> None:
    """
    Actualiza el estado de un job en la tabla ingestion_jobs.

    Args:
        job_id: ID del job a actualizar
        status: Nuevo estado ('completed' o 'failed')
        error_message: Mensaje de error si falló, None si tuvo éxito
        supabase_url: URL de la API de Supabase
        supabase_key: Service role key
    """
    url = f"{supabase_url.rstrip('/')}/rest/v1/ingestion_jobs?id=eq.{job_id}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    update_data = {
        "status": status,
        "error_message": error_message,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.patch(url, json=update_data, headers=headers)
            response.raise_for_status()
            logger.info(f"✅ Job {job_id} actualizado a estado: {status}")

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Error HTTP al actualizar job {job_id}: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"❌ Error al actualizar job {job_id}: {e}")


def main_worker_loop():
    """
    Loop principal del worker con soporte multi-curso.

    Continuamente:
    1. Consulta por nuevos jobs
    2. Crea vector store dinámico basado en el curso del job
    3. Procesa el job
    4. Actualiza el estado
    5. Espera antes de la siguiente iteración
    """
    logger.info("=" * 60)
    logger.info("🚀 INGESTION WORKER STARTED")
    logger.info("=" * 60)

    # Validar configuración
    validate_environment()

    # Configurar LlamaIndex
    configure_llama_index()

    # Inicializar course config service (esto cargará la cache)
    try:
        get_course_config_service()
        logger.info("✅ Course configuration service initialized")
    except Exception as e:
        logger.error(f"❌ Error initializing course config service: {e}")
        logger.error("El worker continuará, pero los jobs fallarán si el curso no existe")

    # Obtener configuración
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    poll_interval = int(os.getenv("WORKER_POLL_INTERVAL", "10"))

    logger.info(f"⏱️  Poll interval: {poll_interval} segundos")
    logger.info("👀 Esperando por nuevos jobs...")
    logger.info("=" * 60)

    job_count = 0

    while True:
        try:
            # 1. Obtener el siguiente job pendiente
            job = dequeue_job(supabase_url, supabase_key)

            if not job:
                # No hay jobs disponibles, esperar
                time.sleep(poll_interval)
                continue

            job_id = job.get('id')
            job_count += 1

            logger.info("")
            logger.info(f"📥 Job #{job_count} obtenido: ID={job_id}")

            # 2. Procesar el job (el vector store se crea dinámicamente dentro)
            status, error_msg = process_job(job)

            # 3. Actualizar el estado del job
            update_job_status(job_id, status, error_msg, supabase_url, supabase_key)

            if status == "completed":
                logger.info(f"✅ Job {job_id} completado exitosamente")
            else:
                logger.error(f"❌ Job {job_id} falló: {error_msg}")

            # Pequeña pausa antes de buscar el siguiente job
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("")
            logger.info("🛑 Worker detenido por el usuario (Ctrl+C)")
            logger.info(f"📊 Total de jobs procesados: {job_count}")
            break

        except Exception as e:
            logger.error(f"🚨 Error inesperado en el worker loop: {e}", exc_info=True)
            logger.warning(f"⏸️  Esperando 30 segundos antes de continuar...")
            time.sleep(30)  # Esperar más tiempo después de un error crítico


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        main_worker_loop()
    except Exception as e:
        logger.critical(f"💥 Error fatal en el worker: {e}", exc_info=True)
        sys.exit(1)
