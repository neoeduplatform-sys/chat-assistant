"""Limit how many chunks from the same document enter rerank / the LLM."""

from __future__ import annotations

import logging
from typing import List, Optional

from app.env_utils import env_int

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle


logger = logging.getLogger(__name__)


def document_key(metadata: Optional[dict]) -> str:
    """Stable key for per-document caps (prefer unique_content_id)."""
    meta = metadata or {}
    uid = meta.get("unique_content_id")
    if uid is not None and str(uid).strip():
        return f"uid:{str(uid).strip()}"
    title = meta.get("title")
    if title is not None and str(title).strip():
        return f"title:{str(title).strip()}"
    topic = meta.get("topic_id")
    if topic is not None and str(topic).strip():
        return f"topic:{str(topic).strip()}"
    return "unknown"


def max_chunks_per_document() -> int:
    return max(0, env_int("MAX_CHUNKS_PER_DOCUMENT", 2))


def is_chunk_diversity_enabled() -> bool:
    return max_chunks_per_document() > 0


class MaxChunksPerDocumentPostprocessor(BaseNodePostprocessor):
    """Keep at most N highest-scoring chunks per document (by metadata key)."""

    def __init__(self, max_per_document: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._max_per_document = max(1, max_per_document)

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        counts: dict[str, int] = {}
        out: List[NodeWithScore] = []
        for nws in nodes:
            key = document_key(nws.node.metadata)
            used = counts.get(key, 0)
            if used >= self._max_per_document:
                continue
            counts[key] = used + 1
            out.append(nws)
        logger.info(
            "Chunk diversity: %d -> %d nodes (max %d per document key)",
            len(nodes),
            len(out),
            self._max_per_document,
        )
        return out

    @classmethod
    def class_name(cls) -> str:
        return "MaxChunksPerDocumentPostprocessor"


def build_chunk_diversity_postprocessor() -> Optional[MaxChunksPerDocumentPostprocessor]:
    n = max_chunks_per_document()
    if n <= 0:
        logger.info("Chunk diversity off: MAX_CHUNKS_PER_DOCUMENT is 0")
        return None
    logger.info("Chunk diversity enabled (max %d per document)", n)
    return MaxChunksPerDocumentPostprocessor(max_per_document=n)
