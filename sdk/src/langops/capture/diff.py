"""Structural state diff — same semantics as the backend ``StateDiffer``.

Top-level channel comparison (LangGraph state is a flat channel map). The
backend recomputes/validates diffs server-side, so this is a convenience for
SDK-side consumers; both sides share the added/modified/removed shape.
"""

from __future__ import annotations

from typing import Any


def diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}

    added = {k: after[k] for k in after.keys() - before.keys()}
    removed = sorted(before.keys() - after.keys())
    modified = {
        k: {"old": before[k], "new": after[k]}
        for k in before.keys() & after.keys()
        if before[k] != after[k]
    }
    return {"added": added, "modified": modified, "removed": removed}
