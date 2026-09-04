"""Parse environment variables (Docker env_file does not strip inline # comments)."""

from __future__ import annotations

import os


def env_raw(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if not value:
        return default
    # Docker Compose env_file: "true # comment" is the full value, not "true".
    return value.split("#", 1)[0].strip().strip('"').strip("'")


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_raw(name, "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    raw = env_raw(name, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default
