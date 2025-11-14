"""
Custom Supabase Vector Store para LlamaIndex
=============================================

Este módulo implementa un vector store personalizado que usa la API REST de Supabase
en lugar de conexión directa a PostgreSQL, evitando problemas con IPv6.
"""

import logging
import httpx
from typing import List, Optional, Any

from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from llama_index.core.schema import BaseNode, TextNode

logger = logging.getLogger(__name__)


class SupabaseVectorStore(BasePydanticVectorStore):
    """
    Vector Store que usa la API REST de Supabase para búsqueda vectorial.

    Esta implementación usa funciones RPC de Supabase para realizar
    búsquedas de similitud vectorial sin necesidad de conexión directa
    a PostgreSQL.
    """

    # Declarar campos de Pydantic
    supabase_url: str
    supabase_key: str
    table_name: str
    rpc_function_name: str
    embed_dim: int = 3072
    match_threshold: float = 0.5
    stores_text: bool = True  # Campo requerido por BasePydanticVectorStore
    is_embedding_query: bool = True  # Campo requerido por BasePydanticVectorStore
    _client: Optional[httpx.Client] = None
    _headers: Optional[dict] = None

    class Config:
        """Configuración de Pydantic."""
        arbitrary_types_allowed = True  # Permitir tipos arbitrarios como httpx.Client
        underscore_attrs_are_private = True  # Los atributos con _ son privados

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        table_name: str,
        rpc_function_name: str,
        embed_dim: int = 3072,
        match_threshold: float = 0.5,
        **kwargs: Any,
    ):
        """
        Inicializa el SupabaseVectorStore.

        Args:
            supabase_url: URL de la API de Supabase
            supabase_key: Service role key de Supabase
            table_name: Nombre de la tabla con vectores
            rpc_function_name: Nombre de la función RPC para búsqueda
            embed_dim: Dimensiones del embedding (default: 3072)
            match_threshold: Umbral de similitud (default: 0.5)
        """
        # Inicializar clase base de Pydantic
        super().__init__(
            supabase_url=supabase_url.rstrip('/'),
            supabase_key=supabase_key,
            table_name=table_name,
            rpc_function_name=rpc_function_name,
            embed_dim=embed_dim,
            match_threshold=match_threshold,
            stores_text=True,
            is_embedding_query=True,
            **kwargs,
        )

        # Headers para autenticación con Supabase
        self._headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }

        # Crear cliente httpx (usar _client interno)
        self._client = httpx.Client(headers=self._headers, timeout=30.0)
        logger.info(f"✅ SupabaseVectorStore inicializado: {self.table_name}")

    @property
    def client(self) -> Any:
        """Retorna la instancia del cliente httpx (requerido por BasePydanticVectorStore)."""
        return self._client

    @property
    def client_instance(self) -> Any:
        """Retorna la instancia del cliente httpx."""
        return self._client

    @classmethod
    def class_name(cls) -> str:
        """Retorna el nombre de la clase."""
        return "SupabaseVectorStore"

    def __del__(self):
        """Cierra el cliente httpx al destruir el objeto."""
        if hasattr(self, '_client'):
            self._client.close()

    def add(self, nodes: List[BaseNode], **add_kwargs: Any) -> List[str]:
        """
        Agrega nodos (documentos) a la tabla de Supabase.

        Args:
            nodes: Lista de nodos a agregar

        Returns:
            Lista de IDs de los nodos agregados
        """
        ids = []
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"

        for node in nodes:
            # Extraer datos del nodo
            embedding = node.get_embedding()
            content = node.get_content()
            metadata = node.metadata or {}

            # Preparar datos para insertar
            data = {
                "content": content,
                "metadata": metadata,
                "embedding": embedding,
            }

            # Insertar en Supabase usando API REST
            try:
                response = self._client.post(
                    url,
                    json=data,
                    headers={"Prefer": "return=representation"}
                )
                response.raise_for_status()

                result = response.json()
                if result and len(result) > 0:
                    node_id = str(result[0].get("id", ""))
                    ids.append(node_id)
                    logger.debug(f"Nodo agregado con ID: {node_id}")
                else:
                    logger.warning(f"No se pudo obtener ID para nodo: {content[:50]}...")

            except httpx.HTTPStatusError as e:
                logger.error(f"Error HTTP al insertar nodo: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error al insertar nodo: {e}")
                raise

        logger.info(f"✅ {len(ids)} nodos agregados a Supabase")
        return ids

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """
        Elimina un documento de la tabla.

        Args:
            ref_doc_id: ID del documento a eliminar
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}?id=eq.{ref_doc_id}"

        try:
            response = self._client.delete(url)
            response.raise_for_status()
            logger.info(f"Documento {ref_doc_id} eliminado")
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al eliminar documento {ref_doc_id}: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error al eliminar documento {ref_doc_id}: {e}")
            raise

    def delete_by_metadata(self, filter_key: str, filter_value: str) -> int:
        """
        Elimina todos los documentos que coincidan con un filtro de metadata.

        Esta función es útil para el patrón "upsert": eliminar todos los chunks
        antiguos de un documento antes de insertar la nueva versión.

        Args:
            filter_key: Clave en el campo metadata (ej: "unique_content_id")
            filter_value: Valor a buscar en esa clave

        Returns:
            Número de documentos eliminados

        Example:
            # Eliminar todos los chunks del documento con unique_content_id="doc123"
            deleted_count = vector_store.delete_by_metadata("unique_content_id", "doc123")
        """
        # Usar PostgREST syntax para query en JSONB
        # metadata->>'key' = 'value'
        # URL encoding: metadata->>key=eq.value
        url = f"{self.supabase_url}/rest/v1/{self.table_name}?metadata->{filter_key}=eq.{filter_value}"

        try:
            # Agregar header para obtener el número de filas afectadas
            delete_headers = {
                **self._headers,
                "Prefer": "return=representation"
            }

            response = self._client.delete(url, headers=delete_headers)
            response.raise_for_status()

            # Contar cuántos documentos fueron eliminados
            deleted_data = response.json()
            deleted_count = len(deleted_data) if deleted_data else 0

            logger.info(f"✅ {deleted_count} documento(s) eliminado(s) con {filter_key}={filter_value}")
            return deleted_count

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Error HTTP al eliminar documentos con {filter_key}={filter_value}: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Error al eliminar documentos con {filter_key}={filter_value}: {e}")
            raise

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        """
        Realiza una búsqueda vectorial usando la función RPC de Supabase.

        Args:
            query: Query con el embedding de búsqueda

        Returns:
            Resultados de la búsqueda
        """
        # Obtener embedding de la query
        query_embedding = query.query_embedding
        if not query_embedding:
            raise ValueError("query_embedding es requerido para la búsqueda")

        # Parámetros para la función RPC
        match_count = query.similarity_top_k or 3

        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "match_threshold": self.match_threshold,
            "filter": {},  # Puedes agregar filtros personalizados aquí
        }

        logger.debug(f"Ejecutando RPC: {self.rpc_function_name} con match_count={match_count}")

        # URL para llamar a la función RPC
        url = f"{self.supabase_url}/rest/v1/rpc/{self.rpc_function_name}"

        # Log INFO para debugging
        logger.info(f"🔍 Calling Supabase RPC: {self.rpc_function_name}")
        logger.info(f"   URL: {url}")
        logger.info(f"   Parameters: match_count={match_count}, threshold={self.match_threshold}")

        try:
            # Llamar a la función RPC de Supabase usando httpx
            response = self._client.post(url, json=rpc_params)
            response.raise_for_status()

            data = response.json()

            # Log de resultados obtenidos
            logger.info(f"📊 RPC Response: {len(data) if data else 0} results returned from Supabase")

            if not data:
                logger.warning("⚠️  No se encontraron resultados para la búsqueda")
                return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])

            # Procesar resultados
            nodes = []
            similarities = []
            ids = []

            for row in data:
                # Crear nodo a partir de los datos
                node = TextNode(
                    text=row.get("content", ""),
                    metadata=row.get("metadata", {}),
                    id_=str(row.get("id", "")),
                )

                nodes.append(node)
                similarities.append(float(row.get("similarity", 0.0)))
                ids.append(str(row.get("id", "")))

            logger.info(f"✅ Búsqueda completada: {len(nodes)} resultados encontrados")
            if nodes:
                first_metadata = nodes[0].metadata
                logger.info(f"   Primera fuente: {first_metadata.get('title', 'N/A')} (similarity: {similarities[0]:.3f})")

            return VectorStoreQueryResult(
                nodes=nodes,
                similarities=similarities,
                ids=ids,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP en búsqueda RPC: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error en búsqueda RPC: {e}")
            raise
