"""Safe serialization of arbitrary LangGraph state.

Converts any value to a JSON-safe form (fallback ``repr`` for the unknown),
bounds depth, and caps the encoded size at ``max_payload_bytes`` with a
``langops.truncated`` marker. Never raises on user data.
"""

from __future__ import annotations

import json
from typing import Any

_MAX_DEPTH = 8
_TRUNCATED = {"langops.truncated": True}


def to_jsonable(value: Any, *, _depth: int = 0) -> Any:
    """Best-effort conversion of ``value`` to JSON-serializable primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if _depth >= _MAX_DEPTH:
        return _repr(value)

    # LangChain messages and pydantic models expose a dict form.
    for attr in ("model_dump", "dict", "to_json"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return to_jsonable(method(), _depth=_depth + 1)
            except Exception:  # noqa: BLE001 — fall through to generic handling
                break

    if isinstance(value, dict):
        return {str(k): to_jsonable(v, _depth=_depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v, _depth=_depth + 1) for v in value]
    return _repr(value)


def _repr(value: Any) -> str:
    try:
        return repr(value)
    except Exception:  # noqa: BLE001
        return f"<unserializable {type(value).__name__}>"


def serialize(jsonable: Any, max_bytes: int) -> tuple[str, bool, int]:
    """Encode to a JSON string; returns ``(json, truncated, size_bytes)``.

    Oversized payloads are replaced by a small truncation marker rather than
    cutting mid-string (which would produce invalid JSON downstream).
    """
    try:
        encoded = json.dumps(jsonable, default=_repr, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        encoded = json.dumps(_repr(jsonable))
    size = len(encoded.encode("utf-8"))
    if size > max_bytes:
        return json.dumps(_TRUNCATED), True, size
    return encoded, False, size


def count_messages(jsonable: Any) -> int | None:
    """Length of a ``messages`` channel, for the context-growth series."""
    if isinstance(jsonable, dict):
        messages = jsonable.get("messages")
        if isinstance(messages, list):
            return len(messages)
    return None
