"""
Chat Memory Service
====================

Implements the 3-layer conversational memory model (see
`project/memory/CONVERSATION_MEMORY_MODEL.md`):

- Layer A — recent literal history, token-budgeted
- Layer B — rolling summary per (user_id, course_id)
- Layer C — RAG (handled outside this module)

This module only owns A and B. Persistence is on Supabase via REST
(same pattern as ``course_config.py``).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


# ============================================================================
# Config (env-driven)
# ============================================================================

def _getenv_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


HISTORY_MAX_TOKENS = _getenv_int("CHAT_HISTORY_MAX_TOKENS", 3500)
SUMMARY_MAX_TOKENS = _getenv_int("CHAT_SUMMARY_MAX_TOKENS", 800)
SUMMARY_REFRESH_EVERY_N_TURNS = _getenv_int("CHAT_SUMMARY_REFRESH_EVERY_N_TURNS", 6)
MAX_MESSAGES_SAFETY = _getenv_int("CHAT_MAX_MESSAGES_SAFETY", 40)


def estimate_tokens(text: str) -> int:
    """Rough char/4 estimate. Good enough for budget-enforcement fallback."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# ============================================================================
# Service
# ============================================================================

class ChatMemoryService:
    """Supabase-backed CRUD for conversations, messages and rolling summaries."""

    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.client = httpx.Client(headers=self.headers, timeout=30.0)
        self._rest = f"{self.supabase_url.rstrip('/')}/rest/v1"

    # -------- conversations -------------------------------------------------

    def resolve_conversation(self, user_id: str, course_id: str) -> str:
        """Return conversation UUID, creating the row on first turn."""
        url = f"{self._rest}/rpc/get_or_create_conversation"
        r = self.client.post(
            url,
            json={"p_user_id": user_id, "p_course_id": course_id},
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            raise RuntimeError("get_or_create_conversation returned empty set")
        return data[0]["id"]

    def find_conversation_id(self, user_id: str, course_id: str) -> Optional[str]:
        """Return conversation UUID if it exists; do not create (for GET history)."""
        url = f"{self._rest}/chat_conversations"
        params = {
            "user_id": f"eq.{user_id}",
            "course_id": f"eq.{course_id}",
            "select": "id",
            "limit": "1",
        }
        r = self.client.get(url, params=params)
        r.raise_for_status()
        rows = r.json() or []
        return rows[0]["id"] if rows else None

    # -------- messages (layer A) --------------------------------------------

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = MAX_MESSAGES_SAFETY,
    ) -> List[Dict[str, str]]:
        """Return most recent messages in chronological (ASC) order."""
        url = f"{self._rest}/chat_messages"
        params = {
            "conversation_id": f"eq.{conversation_id}",
            "select": "role,content,created_at",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        r = self.client.get(url, params=params)
        r.raise_for_status()
        rows = r.json() or []
        rows.reverse()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def list_messages_chronological(
        self,
        conversation_id: str,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return messages in chronological order (oldest first) with ids and timestamps."""
        url = f"{self._rest}/chat_messages"
        params = {
            "conversation_id": f"eq.{conversation_id}",
            "select": "id,role,content,created_at",
            "order": "created_at.asc",
            "limit": str(max(1, min(limit, 500))),
            "offset": str(max(0, offset)),
        }
        r = self.client.get(url, params=params)
        r.raise_for_status()
        return r.json() or []

    @staticmethod
    def tail_page_start_index(total: int, limit: int, offset_from_end: int) -> int:
        """Index (0-based) of the oldest message in a tail page.

        ``offset_from_end`` skips that many messages counting back from the newest.
        Example: total=170, limit=40, offset_from_end=0 → start=130 (last 40 msgs).
        """
        if total <= 0:
            return 0
        return max(0, total - limit - max(0, offset_from_end))

    def list_messages_tail_chronological(
        self,
        conversation_id: str,
        *,
        limit: int = 40,
        offset_from_end: int = 0,
        total_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return the most recent messages in chronological order (oldest first within the page)."""
        total = total_count if total_count is not None else self.count_messages(conversation_id)
        if total <= 0:
            return []
        start = self.tail_page_start_index(total, limit, offset_from_end)
        return self.list_messages_chronological(
            conversation_id,
            limit=min(limit, total - start),
            offset=start,
        )

    def persist_message(self, conversation_id: str, role: str, content: str) -> None:
        if role not in ("user", "assistant"):
            raise ValueError(f"invalid role: {role}")
        url = f"{self._rest}/chat_messages"
        r = self.client.post(
            url,
            json={"conversation_id": conversation_id, "role": role, "content": content},
        )
        r.raise_for_status()

    def count_messages(self, conversation_id: str) -> int:
        url = f"{self._rest}/chat_messages"
        params = {"conversation_id": f"eq.{conversation_id}", "select": "id"}
        headers = {**self.headers, "Prefer": "count=exact", "Range": "0-0"}
        r = self.client.get(url, params=params, headers=headers)
        r.raise_for_status()
        content_range = r.headers.get("content-range", "")
        if "/" in content_range:
            total = content_range.split("/")[-1]
            if total.isdigit():
                return int(total)
        return len(r.json() or [])

    @staticmethod
    def trim_to_token_budget(
        messages: List[Dict[str, str]],
        max_tokens: int = HISTORY_MAX_TOKENS,
    ) -> List[Dict[str, str]]:
        """Keep the tail of ``messages`` under the token budget.

        Walks from the end backwards, dropping the oldest first. If the final
        kept tail starts with an ``assistant`` message whose preceding ``user``
        turn was dropped, drop that orphan assistant too.
        """
        if not messages:
            return []

        kept: List[Dict[str, str]] = []
        running = 0
        for msg in reversed(messages):
            cost = estimate_tokens(msg.get("content", "")) + 4  # +role tag overhead
            if running + cost > max_tokens and kept:
                break
            kept.append(msg)
            running += cost
        kept.reverse()

        # Avoid a dangling assistant with no preceding user turn.
        if kept and kept[0]["role"] == "assistant":
            kept = kept[1:]
        return kept

    # -------- summary (layer B) ---------------------------------------------

    def get_memory_row(self, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self._rest}/user_course_memory"
        params = {
            "user_id": f"eq.{user_id}",
            "course_id": f"eq.{course_id}",
            "select": "summary,message_count_at_last_summary,updated_at",
            "limit": "1",
        }
        r = self.client.get(url, params=params)
        r.raise_for_status()
        rows = r.json() or []
        return rows[0] if rows else None

    def get_summary(self, user_id: str, course_id: str) -> str:
        row = self.get_memory_row(user_id, course_id)
        return (row or {}).get("summary", "") or ""

    def upsert_summary(
        self,
        user_id: str,
        course_id: str,
        summary: str,
        message_count: int,
    ) -> None:
        url = f"{self._rest}/user_course_memory"
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        payload = {
            "user_id": user_id,
            "course_id": course_id,
            "summary": summary,
            "message_count_at_last_summary": message_count,
        }
        r = self.client.post(url, json=payload, headers=headers)
        r.raise_for_status()

    # -------- prompt composition --------------------------------------------

    @staticmethod
    def format_history_block(messages: List[Dict[str, str]]) -> str:
        if not messages:
            return ""
        lines = []
        for m in messages:
            speaker = "Usuario" if m["role"] == "user" else "Asistente"
            lines.append(f"{speaker}: {m['content']}")
        return "\n".join(lines)

    @staticmethod
    def build_composed_query_str(
        summary: str,
        history: List[Dict[str, str]],
        question: str,
    ) -> str:
        """Compose layer-B + layer-A + current question into the query_str.

        ``context_str`` (layer C) is filled separately by the query engine.
        """
        parts: List[str] = []
        if summary and summary.strip():
            parts.append(
                "Resumen de la conversación previa con este estudiante en este curso:\n"
                f"{summary.strip()}"
            )
        history_block = ChatMemoryService.format_history_block(history)
        if history_block:
            parts.append(
                "Historial reciente de la conversación:\n"
                f"{history_block}"
            )
        parts.append(f"Pregunta actual: {question}")
        return "\n\n".join(parts)

    # -------- summary refresh policy ----------------------------------------

    def should_refresh_summary(
        self,
        total_messages: int,
        last_summary_count: int,
    ) -> bool:
        """Refresh when N or more new turns (user+assistant pairs) have landed
        since the last summary. A "turn" == 2 messages.
        """
        new_messages = max(0, total_messages - last_summary_count)
        return (new_messages // 2) >= SUMMARY_REFRESH_EVERY_N_TURNS


# ============================================================================
# Summarization (stateless helper — uses the global LlamaIndex LLM)
# ============================================================================

def summarize_conversation(
    previous_summary: str,
    recent_messages: List[Dict[str, str]],
) -> str:
    """Produce a new rolling summary in Spanish.

    Uses whatever LLM is configured in llama_index Settings. Kept in this
    module so callers don't have to know which LLM driver is active.
    """
    from llama_index.core import Settings

    if not recent_messages:
        return previous_summary or ""

    llm = Settings.llm
    if llm is None:
        logger.warning("No LLM configured; skipping summary refresh.")
        return previous_summary or ""

    history_block = ChatMemoryService.format_history_block(recent_messages)
    prior = previous_summary.strip() if previous_summary else "(sin resumen previo)"

    prompt = (
        "Eres un asistente que mantiene un resumen acumulado de la conversación "
        "entre un estudiante y un asistente educativo, dentro de un curso concreto.\n\n"
        "Debes producir un NUEVO resumen en español, conciso y orientado a "
        "recordar hechos útiles para responder preguntas futuras:\n"
        "- Temas y subtemas que el estudiante ya consultó\n"
        "- Definiciones, acuerdos o aclaraciones que ya se dieron\n"
        "- Preferencias o dudas recurrentes del estudiante\n"
        "- Evita detalles irrelevantes o repeticiones\n\n"
        f"Resumen previo:\n{prior}\n\n"
        f"Mensajes recientes (cronológicos):\n{history_block}\n\n"
        "Nuevo resumen (máx ~200 palabras, en español, sin encabezados):"
    )

    try:
        response = llm.complete(prompt)
        text = getattr(response, "text", None) or str(response)
        return text.strip()
    except Exception as exc:
        logger.error("Summary refresh failed: %s", exc, exc_info=True)
        return previous_summary or ""


# ============================================================================
# Singleton accessor
# ============================================================================

_service: Optional[ChatMemoryService] = None


def get_chat_memory_service() -> ChatMemoryService:
    global _service
    if _service is None:
        _service = ChatMemoryService()
    return _service
