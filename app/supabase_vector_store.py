"""
Custom Supabase Vector Store para LlamaIndex
=============================================

Este módulo implementa un vector store personalizado que usa la API REST de Supabase
en lugar de conexión directa a PostgreSQL, evitando problemas con IPv6.
"""

import logging
import httpx
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, PrivateAttr

from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from llama_index.core.schema import BaseNode, TextNode

from app.rpc_filter import (
    filter_empty,
    filter_has_topic_id,
    is_retrieval_merge_with_topic_id_enabled,
    is_topic_priority_retrieval_enabled,
    topic_priority_min_phase1_results,
)


def _advanced_retrieval_active() -> bool:
    from app.chunk_diversity import is_chunk_diversity_enabled
    from app.cohere_rerank import is_rerank_active

    return is_rerank_active() or is_chunk_diversity_enabled()


def _use_two_phase_retrieval() -> bool:
    if is_topic_priority_retrieval_enabled():
        return True
    return is_retrieval_merge_with_topic_id_enabled() and _advanced_retrieval_active()


def _two_phase_always_merge() -> bool:
    """Fusionar fase curricular + global (no cortar solo en fase 1)."""
    if is_topic_priority_retrieval_enabled():
        from app.env_utils import env_bool

        return env_bool("TOPIC_PRIORITY_ALWAYS_MERGE", default=False)
    return True
from app.source_labels import metadata_source_label

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

    model_config = ConfigDict(arbitrary_types_allowed=True)
    _client: Optional[httpx.Client] = PrivateAttr(default=None)
    _headers: Optional[dict] = PrivateAttr(default=None)

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
        url = f"{self.supabase_url}/rest/v1/{self.table_name}?metadata->>{filter_key}=eq.{filter_value}"

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

    @staticmethod
    def merge_query_results(
        primary: VectorStoreQueryResult,
        secondary: VectorStoreQueryResult,
        max_count: int,
    ) -> VectorStoreQueryResult:
        """Une resultados priorizando ``primary`` (p. ej. chunks con topic_id)."""
        seen: set[str] = set()
        nodes: List[TextNode] = []
        similarities: List[float] = []
        ids: List[str] = []

        for batch in (primary, secondary):
            for node, sim, node_id in zip(batch.nodes, batch.similarities, batch.ids):
                if node_id in seen:
                    continue
                seen.add(node_id)
                nodes.append(node)
                similarities.append(sim)
                ids.append(node_id)
                if len(nodes) >= max_count:
                    break
            if len(nodes) >= max_count:
                break

        return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

    def _rows_to_query_result(self, data: Optional[List[dict]]) -> VectorStoreQueryResult:
        if not data:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])

        nodes: List[TextNode] = []
        similarities: List[float] = []
        ids: List[str] = []

        for row in data:
            node = TextNode(
                text=row.get("content", ""),
                metadata=row.get("metadata", {}),
                id_=str(row.get("id", "")),
            )
            nodes.append(node)
            similarities.append(float(row.get("similarity", 0.0)))
            ids.append(str(row.get("id", "")))

        return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

    def _call_rpc(
        self,
        query_embedding: List[float],
        match_count: int,
        metadata_filter: Dict[str, Any],
    ) -> VectorStoreQueryResult:
        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "match_threshold": self.match_threshold,
            "filter": metadata_filter,
        }
        url = f"{self.supabase_url}/rest/v1/rpc/{self.rpc_function_name}"
        filter_label = metadata_filter if metadata_filter else "(sin filtro)"

        logger.info(
            "🔍 RPC %s | match_count=%s threshold=%s filter=%s",
            self.rpc_function_name,
            match_count,
            self.match_threshold,
            filter_label,
        )

        response = self._client.post(url, json=rpc_params)
        response.raise_for_status()
        data = response.json()
        count = len(data) if data else 0
        logger.info("📊 RPC Response: %d result(s)", count)
        return self._rows_to_query_result(data)

    def _query_single(
        self,
        query_embedding: List[float],
        match_count: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> VectorStoreQueryResult:
        filt = metadata_filter if metadata_filter is not None else filter_empty()
        try:
            result = self._call_rpc(query_embedding, match_count, filt)
        except httpx.HTTPStatusError as e:
            if filt and e.response.status_code in (400, 404):
                logger.warning(
                    "RPC rechazó filter=%s (%s). ¿Ejecutaste migrations/004_rpc_metadata_filter.sql "
                    "y actualizaste la función match_*? Reintentando sin filtro.",
                    filt,
                    e.response.status_code,
                )
                result = self._call_rpc(query_embedding, match_count, filter_empty())
            else:
                logger.error(
                    "Error HTTP en búsqueda RPC: %s - %s",
                    e.response.status_code,
                    e.response.text,
                )
                raise

        if result.nodes:
            first_label = metadata_source_label(result.nodes[0].metadata) or "N/A"
            logger.info(
                "   Primera fuente: %s (similarity: %.3f)",
                first_label,
                result.similarities[0],
            )
        return result

    def _query_topic_priority_two_phase(
        self,
        query_embedding: List[float],
        match_count: int,
    ) -> VectorStoreQueryResult:
        min_phase1 = topic_priority_min_phase1_results()
        always_merge = _two_phase_always_merge()

        phase1 = self._query_single(query_embedding, match_count, filter_has_topic_id())
        n1 = len(phase1.nodes)
        logger.info(
            "📚 Búsqueda fase 1 (has_topic_id): %d/%d resultados",
            n1,
            match_count,
        )

        if not always_merge and n1 >= min_phase1:
            logger.info(
                "✅ Fase 1 suficiente (>=%d); no se amplía búsqueda sin filtro",
                min_phase1,
            )
            return phase1

        phase2 = self._query_single(query_embedding, match_count, filter_empty())
        n2 = len(phase2.nodes)
        logger.info("📚 Búsqueda fase 2 (sin filtro): %d resultados", n2)

        merged = self.merge_query_results(phase1, phase2, match_count)
        logger.info(
            "✅ Búsqueda two-phase fusionada: fase1=%d + fase2=%d → %d candidatos",
            n1,
            n2,
            len(merged.nodes),
        )
        return merged

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        """
        Realiza una búsqueda vectorial usando la función RPC de Supabase.

        Con diversidad/rerank y ``RETRIEVAL_MERGE_WITH_TOPIC_ID=true`` (default):
        fusiona fase ``has_topic_id`` + búsqueda global.
        """
        query_embedding = query.query_embedding
        if not query_embedding:
            raise ValueError("query_embedding es requerido para la búsqueda")

        match_count = query.similarity_top_k or 3

        try:
            if _use_two_phase_retrieval():
                result = self._query_topic_priority_two_phase(query_embedding, match_count)
            else:
                result = self._query_single(query_embedding, match_count, filter_empty())

            if not result.nodes:
                logger.warning("⚠️  No se encontraron resultados para la búsqueda")
            elif len(result.nodes) < match_count:
                logger.info(
                    "ℹ️  RPC devolvió %d/%d (umbral %.2f puede limitar candidatos)",
                    len(result.nodes),
                    match_count,
                    self.match_threshold,
                )

            logger.info("✅ Búsqueda completada: %d resultado(s)", len(result.nodes))

            logger.info("[RAG_DB_RESULTS] %d initial chunks from Supabase:", len(result.nodes))
            for n, sim in zip(result.nodes, result.similarities or []):
                logger.info(
                    "  • db_id=%s | unique_content_id=%s | similarity=%.4f",
                    n.id_,
                    (n.metadata or {}).get("unique_content_id", "N/A"),
                    sim,
                )

            return result

        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error("Error en búsqueda RPC: %s", e)
            raise
