"""
Per-request LLM token usage tracking + cost computation.
======================================================

A single ``/api/chat`` request may trigger up to two LLM calls (RAG synthesis and
the rolling-memory summary refresh), both sharing the global ``Settings.llm``.

This module accumulates token usage across *all* LLM calls that happen within a
single request using a :class:`contextvars.ContextVar`. Unlike a shared/global
``TokenCountingHandler``, a ContextVar gives every request (even under FastAPI's
async concurrency) its own isolated accumulator, so counts never bleed between
concurrent requests.

Usage:
    1. Register the handler once (globally) after ``Settings.llm`` is set::

        Settings.callback_manager = CallbackManager([TokenTrackerCallbackHandler()])

    2. At the start of a request handler, install a fresh accumulator::

        start_request_tracking()

    3. Read the totals before returning the response::

        usage = get_current_usage()
        cost = compute_cost(model_name, usage.input_tokens, usage.output_tokens)
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llama_index.core.callbacks.base_handler import BaseCallbackHandler
from llama_index.core.callbacks.schema import CBEventType, EventPayload

logger = logging.getLogger(__name__)


# ============================================================================
# Request-local accumulator
# ============================================================================

@dataclass
class TokenUsageAccumulator:
    """Running token totals for a single request."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0

    def add(self, input_tokens: int, output_tokens: int, total_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        # Fall back to input+output when the provider doesn't report a total.
        self.total_tokens += total_tokens or (input_tokens + output_tokens)
        self.llm_calls += 1


# Each request gets its own value; default None = no tracking active (e.g. worker).
_token_usage: ContextVar[Optional[TokenUsageAccumulator]] = ContextVar(
    "token_usage", default=None
)


def start_request_tracking() -> TokenUsageAccumulator:
    """Install a fresh accumulator on the ContextVar for the current request."""
    acc = TokenUsageAccumulator()
    _token_usage.set(acc)
    return acc


def get_current_usage() -> Optional[TokenUsageAccumulator]:
    """Return the accumulator for the current request, or None if not tracking."""
    return _token_usage.get()


# ============================================================================
# Extracting token counts from an LLM response payload
# ============================================================================

def _extract_token_counts(response: Any) -> Optional[tuple[int, int, int]]:
    """Return (input, output, total) tokens from a LlamaIndex LLM response.

    Primary source: ``response.additional_kwargs`` populated by
    ``llama-index-llms-google-genai`` with ``prompt_tokens`` / ``completion_tokens``
    / ``total_tokens``.

    Fallback: the native Google response under ``response.raw.usage_metadata`` with
    ``prompt_token_count`` / ``candidates_token_count`` / ``total_token_count``.
    """
    # Primary: LlamaIndex additional_kwargs
    kwargs = getattr(response, "additional_kwargs", None)
    if isinstance(kwargs, dict):
        prompt = kwargs.get("prompt_tokens")
        completion = kwargs.get("completion_tokens")
        total = kwargs.get("total_tokens")
        if prompt is not None or completion is not None or total is not None:
            return int(prompt or 0), int(completion or 0), int(total or 0)

    # Fallback: native Google usage_metadata
    raw = getattr(response, "raw", None)
    usage = getattr(raw, "usage_metadata", None) if raw is not None else None
    if usage is None and isinstance(raw, dict):
        usage = raw.get("usage_metadata")
    if usage is not None:
        def _get(obj: Any, key: str) -> int:
            val = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
            return int(val or 0)

        prompt = _get(usage, "prompt_token_count")
        completion = _get(usage, "candidates_token_count")
        total = _get(usage, "total_token_count")
        if prompt or completion or total:
            return prompt, completion, total

    return None


# ============================================================================
# Callback handler
# ============================================================================

class TokenTrackerCallbackHandler(BaseCallbackHandler):
    """LlamaIndex callback that feeds LLM token usage into the request accumulator."""

    def __init__(self) -> None:
        super().__init__(
            event_starts_to_ignore=[],
            event_ends_to_ignore=[],
        )

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        if event_type != CBEventType.LLM or not payload:
            return

        acc = _token_usage.get()
        if acc is None:
            # No active request tracking (e.g. worker/ingest path) -> no-op.
            return

        response = payload.get(EventPayload.RESPONSE)
        if response is None:
            return

        counts = _extract_token_counts(response)
        if counts is None:
            logger.debug("Token usage not found in LLM response payload")
            return

        input_tokens, output_tokens, total_tokens = counts
        acc.add(input_tokens, output_tokens, total_tokens)

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        return None

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        return None


# ============================================================================
# Cost computation (env-configurable rates)
# ============================================================================

def compute_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Compute request cost in USD from env-configured per-1M-token rates.

    Rates apply to the configured ``GEMINI_MODEL``. Both default to 0.0 so cost is
    simply 0 until rates are configured.

    Env vars:
        GEMINI_INPUT_PRICE_PER_1M   USD per 1M input (prompt) tokens
        GEMINI_OUTPUT_PRICE_PER_1M  USD per 1M output (completion) tokens
    """
    try:
        input_rate = float(os.getenv("GEMINI_INPUT_PRICE_PER_1M", "0") or 0)
        output_rate = float(os.getenv("GEMINI_OUTPUT_PRICE_PER_1M", "0") or 0)
    except ValueError:
        logger.warning("Invalid GEMINI_*_PRICE_PER_1M env value; treating cost as 0")
        return 0.0

    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
