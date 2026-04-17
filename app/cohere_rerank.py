import logging
import os
from typing import Any, List, Optional

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from pydantic import PrivateAttr


logger = logging.getLogger(__name__)


class _RerankChunkLogger(BaseNodePostprocessor):
    """Envuelve el reranker y registra cuántos chunks entran y salen."""

    _inner: Any = PrivateAttr()

    def __init__(self, inner: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._inner = inner

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        n_in = len(nodes)
        out = self._inner.postprocess_nodes(nodes, query_bundle=query_bundle)
        n_out = len(out)
        logger.info(
            "Cohere rerank: %d chunks from vector retrieval -> %d chunks after rerank",
            n_in,
            n_out,
        )
        return out

    @classmethod
    def class_name(cls) -> str:
        return "RerankChunkLogger"


def _cohere_rerank_enabled() -> bool:
    v = os.getenv("COHERE_RERANK_ENABLED", "false").lower()
    return v in ("1", "true", "yes")


def is_rerank_active() -> bool:
    """True iff rerank should run: flag on and API key present."""
    if not _cohere_rerank_enabled():
        return False
    return bool(os.getenv("COHERE_API_KEY", "").strip())


def build_cohere_rerank_postprocessors() -> List:
    if not _cohere_rerank_enabled():
        logger.info(
            "Cohere rerank off: COHERE_RERANK_ENABLED is not true "
            "(use true, 1, or yes to enable)"
        )
        return []
    if not os.getenv("COHERE_API_KEY", "").strip():
        logger.info("Cohere rerank off: COHERE_API_KEY is missing or empty")
        return []
    api_key = os.getenv("COHERE_API_KEY")
    try:
        from llama_index.postprocessor.cohere_rerank import CohereRerank
    except ImportError as e:
        logger.warning("Cohere rerank package not available: %s", e)
        return []

    top_n = int(os.getenv("RERANK_TOP_N", "4"))
    model = os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5")
    try:
        rerank = CohereRerank(api_key=api_key, top_n=top_n, model=model)
        postprocessors = [_RerankChunkLogger(inner=rerank)]
        logger.info("Cohere rerank enabled (model=%s, top_n=%d)", model, top_n)
        return postprocessors
    except Exception as e:
        logger.warning("Failed to build CohereRerank: %s", e)
        return []


def effective_similarity_top_k() -> int:
    if not is_rerank_active():
        return int(os.getenv("SIMILARITY_TOP_K", "3"))
    k = int(os.getenv("VECTOR_RETRIEVAL_K", os.getenv("SIMILARITY_TOP_K", "10")))
    n = int(os.getenv("RERANK_TOP_N", "4"))
    return max(k, n)
