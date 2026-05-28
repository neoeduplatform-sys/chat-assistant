"""
Filtros JSON para funciones RPC match_* de Supabase (parámetro ``filter``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.env_utils import env_bool, env_int


def is_topic_priority_retrieval_enabled() -> bool:
    """Activa búsqueda en dos fases (primero chunks con topic_id)."""
    return env_bool("TOPIC_PRIORITY_RETRIEVAL", default=False)


def is_retrieval_merge_with_topic_id_enabled() -> bool:
    """
    Fase 1 (has_topic_id) + fase 2 (sin filtro), siempre fusionadas.
    Por defecto on con diversidad o rerank; ver supabase_vector_store.query().
    """
    return env_bool("RETRIEVAL_MERGE_WITH_TOPIC_ID", default=True)


def topic_priority_min_phase1_results() -> int:
    """Mínimo de resultados en fase 1 antes de omitir la ampliación sin filtro."""
    return max(1, env_int("TOPIC_PRIORITY_MIN_RESULTS", 3))


def filter_has_topic_id() -> Dict[str, Any]:
    """Solo chunks cuyo metadata incluye topic_id no vacío (requiere SQL en Supabase)."""
    return {"has_topic_id": True}


def filter_empty() -> Dict[str, Any]:
    return {}


def filter_by_topic_id(topic_id: str) -> Dict[str, Any]:
    """Filtro estricto por un topic_id concreto (uso futuro / API)."""
    return {"topic_id": topic_id.strip()}
