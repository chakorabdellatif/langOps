"""User-pluggable payload scrubbing.

The redaction hook runs on every captured payload *before* it reaches the
exporter, so secrets never leave the process. A failing hook must not break
capture — on error the payload is dropped closed (replaced with a marker)
rather than leaked unredacted.
"""

from __future__ import annotations

from typing import Any

from langops.config import RedactionHook

_REDACTION_FAILED = {"langops.redaction_error": True}


def apply(value: Any, hook: RedactionHook | None) -> Any:
    if hook is None:
        return value
    try:
        return hook(value)
    except Exception:  # noqa: BLE001 — fail closed; never emit unredacted data
        return _REDACTION_FAILED
