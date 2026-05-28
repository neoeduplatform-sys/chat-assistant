"""Tests for per-document chunk cap and retrieval postprocessor pipeline."""

import os
from unittest import mock

from llama_index.core.schema import NodeWithScore, TextNode

from app.chunk_diversity import (
    MaxChunksPerDocumentPostprocessor,
    document_key,
    max_chunks_per_document,
)
from app.cohere_rerank import build_retrieval_postprocessors, effective_similarity_top_k


def _nws(nid: str, uid: str, score: float) -> NodeWithScore:
    node = TextNode(
        text=f"text-{nid}",
        metadata={"unique_content_id": uid, "title": f"Title {uid}"},
        id_=nid,
    )
    return NodeWithScore(node=node, score=score)


def test_document_key_prefers_unique_content_id():
    assert document_key({"unique_content_id": "abc", "title": "X"}) == "uid:abc"
    assert document_key({"title": "Only title"}) == "title:Only title"
    assert document_key({}) == "unknown"


def test_max_chunks_per_document_limits_duplicates():
    proc = MaxChunksPerDocumentPostprocessor(max_per_document=2)
    nodes = [
        _nws("1", "doc-a", 0.9),
        _nws("2", "doc-a", 0.8),
        _nws("3", "doc-a", 0.7),
        _nws("4", "doc-b", 0.65),
    ]
    out = proc.postprocess_nodes(nodes)
    assert len(out) == 3
    assert [n.node.node_id for n in out] == ["1", "2", "4"]


def test_effective_similarity_top_k_with_diversity():
    with mock.patch.dict(
        os.environ,
        {
            "SIMILARITY_TOP_K": "5",
            "VECTOR_RETRIEVAL_K": "40",
            "MAX_CHUNKS_PER_DOCUMENT": "2",
            "COHERE_RERANK_ENABLED": "false",
        },
        clear=False,
    ):
        assert effective_similarity_top_k() == 40


def test_build_retrieval_postprocessors_includes_diversity():
    with mock.patch.dict(
        os.environ,
        {
            "MAX_CHUNKS_PER_DOCUMENT": "2",
            "COHERE_RERANK_ENABLED": "false",
        },
        clear=False,
    ):
        procs = build_retrieval_postprocessors()
    assert len(procs) == 1
    assert procs[0].class_name() == "MaxChunksPerDocumentPostprocessor"


def test_max_chunks_per_document_zero_disables():
    with mock.patch.dict(os.environ, {"MAX_CHUNKS_PER_DOCUMENT": "0"}, clear=False):
        assert max_chunks_per_document() == 0
