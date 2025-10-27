"""
Script de Ingesta de Datos para el Chatbot Educativo
=====================================================

Este script carga documentos desde el directorio ./data, los procesa
y los almacena en ChromaDB para su uso en el sistema RAG.

Uso:
    docker-compose run --rm fastapi_app python ingest.py

    O si quieres ejecutarlo sin Docker:
    python ingest.py
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

import chromadb
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings,
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.core.node_parser import SentenceSplitter

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_environment():
    """Valida que todas las variables de entorno necesarias estén configuradas."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("❌ La variable de entorno GOOGLE_API_KEY no está configurada.")
        logger.error("Por favor, sigue las instrucciones en SETUP_API_KEY.md")
        sys.exit(1)

    logger.info("✅ Variables de entorno validadas correctamente.")
    return api_key


def check_data_directory():
    """Verifica que el directorio de datos exista y contenga archivos."""
    data_path = Path("./data")

    if not data_path.exists():
        logger.error(f"❌ El directorio {data_path} no existe.")
        logger.info("Creando directorio ./data...")
        data_path.mkdir(parents=True, exist_ok=True)
        logger.warning("⚠️  El directorio está vacío. Agrega tus documentos del curso aquí.")
        sys.exit(1)

    # Listar archivos en el directorio
    files = list(data_path.glob("*.*"))
    if not files:
        logger.error("❌ El directorio ./data está vacío.")
        logger.info("Agrega tus documentos del curso (PDF, TXT, MD, etc.) en ./data")
        sys.exit(1)

    logger.info(f"✅ Se encontraron {len(files)} archivos en ./data:")
    for file in files:
        logger.info(f"   - {file.name}")

    return True


def configure_llama_index():
    """Configura los componentes globales de LlamaIndex."""
    # Obtener configuración de variables de entorno con valores por defecto
    model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
    embedding_model = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
    chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "20"))

    logger.info("📝 Configurando LlamaIndex con:")
    logger.info(f"   - Modelo LLM: {model}")
    logger.info(f"   - Modelo de Embeddings: {embedding_model}")
    logger.info(f"   - Tamaño de chunks: {chunk_size}")
    logger.info(f"   - Overlap de chunks: {chunk_overlap}")

    # Configurar componentes
    Settings.llm = GoogleGenAI(model=model)
    Settings.embed_model = GoogleGenAIEmbedding(model_name=embedding_model)
    Settings.node_parser = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    logger.info("✅ LlamaIndex configurado correctamente.")


def load_documents():
    """Carga los documentos desde el directorio ./data."""
    logger.info("📚 Cargando documentos desde ./data...")

    try:
        documents = SimpleDirectoryReader(
            "./data",
            recursive=True,
            required_exts=[".pdf", ".txt", ".md", ".docx", ".doc"]
        ).load_data()

        logger.info(f"✅ Se cargaron {len(documents)} documentos exitosamente.")

        # Mostrar información sobre los documentos
        for i, doc in enumerate(documents, 1):
            logger.info(f"   Documento {i}: {len(doc.text)} caracteres")

        return documents

    except Exception as e:
        logger.error(f"❌ Error al cargar documentos: {e}")
        sys.exit(1)


def connect_to_chromadb():
    """Establece conexión con ChromaDB y obtiene/crea la colección."""
    chromadb_host = os.getenv("CHROMADB_HOST", "chromadb")
    chromadb_port = int(os.getenv("CHROMADB_PORT", "8000"))
    collection_name = os.getenv("COLLECTION_NAME", "course_content")

    logger.info(f"🔌 Conectando a ChromaDB en {chromadb_host}:{chromadb_port}...")

    try:
        # Conectar a ChromaDB
        db = chromadb.HttpClient(host=chromadb_host, port=chromadb_port)

        # Verificar conexión
        db.heartbeat()
        logger.info("✅ Conexión a ChromaDB exitosa.")

        # Obtener o crear colección
        logger.info(f"📦 Obteniendo/creando colección '{collection_name}'...")

        # Primero, intentar eliminar la colección si existe (para reiniciar)
        try:
            db.delete_collection(name=collection_name)
            logger.info(f"🗑️  Colección existente '{collection_name}' eliminada.")
        except:
            pass

        chroma_collection = db.get_or_create_collection(collection_name)
        logger.info(f"✅ Colección '{collection_name}' lista.")

        return chroma_collection

    except Exception as e:
        logger.error(f"❌ Error al conectar con ChromaDB: {e}")
        logger.error("Asegúrate de que ChromaDB está en ejecución:")
        logger.error("   docker-compose up -d chromadb")
        sys.exit(1)


def create_vector_index(documents, chroma_collection):
    """Crea el índice vectorial a partir de los documentos."""
    logger.info("🚀 Creando índice vectorial...")
    logger.info("⏳ Este proceso puede tardar varios minutos dependiendo del tamaño de los documentos...")

    try:
        # Crear el vector store
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Crear el índice
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )

        logger.info("✅ Índice vectorial creado y almacenado en ChromaDB exitosamente.")

        # Mostrar estadísticas
        collection_count = chroma_collection.count()
        logger.info(f"📊 Estadísticas:")
        logger.info(f"   - Total de fragmentos (chunks) almacenados: {collection_count}")

        return index

    except Exception as e:
        logger.error(f"❌ Error al crear el índice vectorial: {e}")
        sys.exit(1)


def main():
    """Función principal del script de ingesta."""
    logger.info("=" * 70)
    logger.info("  SCRIPT DE INGESTA DE DATOS - CHATBOT EDUCATIVO")
    logger.info("=" * 70)

    # 1. Validar entorno
    validate_environment()

    # 2. Verificar directorio de datos
    check_data_directory()

    # 3. Configurar LlamaIndex
    configure_llama_index()

    # 4. Cargar documentos
    documents = load_documents()

    # 5. Conectar a ChromaDB
    chroma_collection = connect_to_chromadb()

    # 6. Crear índice vectorial
    create_vector_index(documents, chroma_collection)

    logger.info("=" * 70)
    logger.info("  ✅ PROCESO DE INGESTA COMPLETADO EXITOSAMENTE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Próximos pasos:")
    logger.info("  1. Inicia la API: docker-compose up -d")
    logger.info("  2. Prueba el chatbot en: http://localhost:8080")
    logger.info("")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Proceso interrumpido por el usuario.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Error inesperado: {e}")
        sys.exit(1)
