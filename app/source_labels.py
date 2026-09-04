"""
Etiquetas legibles para fuentes RAG a partir de metadata de chunks.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

_SOURCE_LABEL_KEYS = (
    "title",
    "file_name",
    "unique_content_id",
    "document",
    "topic",
    "content",
    "type",
)

_MAX_SOURCE_LABEL_LEN = 120


def metadata_source_label(metadata: Optional[Mapping[str, Any]]) -> Optional[str]:
    """
    Devuelve una etiqueta humana para mostrar como fuente del chunk.

    Prioriza campos del contrato API (title, file_name, unique_content_id) y
    hace fallback a campos típicos de ingesta blob/LlamaIndex (document, topic, …).
    """
    if not metadata:
        return None

    for key in _SOURCE_LABEL_KEYS:
        raw = metadata.get(key)
        if raw is None:
            continue
        label = str(raw).strip()
        if not label:
            continue
        if len(label) > _MAX_SOURCE_LABEL_LEN:
            return label[: _MAX_SOURCE_LABEL_LEN - 1] + "…"
        return label

    return None
