"""Tests for two-phase topic_id retrieval helpers."""

from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import VectorStoreQueryResult

from app.rpc_filter import filter_has_topic_id, filter_empty
from app.supabase_vector_store import SupabaseVectorStore


def _node(nid: str, topic: str | None = None) -> TextNode:
    meta = {"topic_id": topic} if topic else {}
    return TextNode(text=f"chunk-{nid}", metadata=meta, id_=nid)


def test_filter_has_topic_id_shape():
    assert filter_has_topic_id() == {"has_topic_id": True}
    assert filter_empty() == {}


def test_merge_prioritizes_primary_and_dedupes():
    primary = VectorStoreQueryResult(
        nodes=[_node("1", "MI017"), _node("2", "MI017")],
        similarities=[0.9, 0.8],
        ids=["1", "2"],
    )
    secondary = VectorStoreQueryResult(
        nodes=[_node("2", "MI017"), _node("3")],
        similarities=[0.85, 0.7],
        ids=["2", "3"],
    )
    merged = SupabaseVectorStore.merge_query_results(primary, secondary, max_count=10)
    assert merged.ids == ["1", "2", "3"]
    assert len(merged.nodes) == 3


def test_merge_respects_max_count():
    primary = VectorStoreQueryResult(
        nodes=[_node("1", "A")],
        similarities=[0.9],
        ids=["1"],
    )
    secondary = VectorStoreQueryResult(
        nodes=[_node("2"), _node("3")],
        similarities=[0.8, 0.7],
        ids=["2", "3"],
    )
    merged = SupabaseVectorStore.merge_query_results(primary, secondary, max_count=2)
    assert merged.ids == ["1", "2"]
