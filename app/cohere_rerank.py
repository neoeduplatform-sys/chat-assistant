import logging
import os
from typing import Any, List, Optional

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from pydantic import PrivateAttr

from app.chunk_diversity import (
    build_chunk_diversity_postprocessor,
    is_chunk_diversity_enabled,
)
from app.env_utils import env_bool, env_int, env_raw


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
    return env_bool("COHERE_RERANK_ENABLED", default=False)


def is_rerank_active() -> bool:
    """True iff rerank should run: flag on and API key present."""
    if not _cohere_rerank_enabled():
        return False
    return bool(env_raw("COHERE_API_KEY", "").strip())


def build_cohere_rerank_postprocessors() -> List:
    if not _cohere_rerank_enabled():
        logger.info(
            "Cohere rerank off: COHERE_RERANK_ENABLED=%r (use true, 1, or yes)",
            env_raw("COHERE_RERANK_ENABLED", "(unset)"),
        )
        return []
    api_key = env_raw("COHERE_API_KEY", "")
    if not api_key:
        logger.info("Cohere rerank off: COHERE_API_KEY is missing or empty")
        return []
    try:
        from llama_index.postprocessor.cohere_rerank import CohereRerank
    except ImportError as e:
        logger.warning("Cohere rerank package not available: %s", e)
        return []

    top_n = env_int("RERANK_TOP_N", 4)
    model = env_raw("COHERE_RERANK_MODEL", "rerank-v3.5")
    try:
        rerank = CohereRerank(api_key=api_key, top_n=top_n, model=model)
        postprocessors = [_RerankChunkLogger(inner=rerank)]
        logger.info("Cohere rerank enabled (model=%s, top_n=%d)", model, top_n)
        return postprocessors
    except Exception as e:
        logger.warning("Failed to build CohereRerank: %s", e)
        return []


def effective_similarity_top_k() -> int:
    base = env_int("SIMILARITY_TOP_K", 3)
    if not is_rerank_active() and not is_chunk_diversity_enabled():
        return base
    k = env_int("VECTOR_RETRIEVAL_K", 40)
    if is_rerank_active():
        n = env_int("RERANK_TOP_N", 4)
        return max(k, n, base)
    return max(k, base)


def build_retrieval_postprocessors() -> List:
    """
    Postprocessors after vector retrieval, in order:
    1) cap chunks per document, 2) Cohere rerank (if enabled).
    """
    postprocessors: List = []
    diversity = build_chunk_diversity_postprocessor()
    if diversity is not None:
        postprocessors.append(diversity)
    postprocessors.extend(build_cohere_rerank_postprocessors())
    return postprocessors
