"""Structural diff between two JSON-like states.

Top-level key comparison: LangGraph state is a flat channel map, so diffing
at channel granularity is what the dashboard visualizes. Values are compared
by equality; nested drill-down is a dashboard concern.
"""

from typing import Any

from langops_api.domain.value_objects import StateDiff


class StateDiffer:
    def diff(self, before: dict[str, Any] | None, after: dict[str, Any] | None) -> StateDiff:
        before = before if isinstance(before, dict) else {}
        after = after if isinstance(after, dict) else {}

        added = {key: after[key] for key in after.keys() - before.keys()}
        removed = sorted(before.keys() - after.keys())
        modified = {
            key: {"old": before[key], "new": after[key]}
            for key in before.keys() & after.keys()
            if before[key] != after[key]
        }
        return StateDiff(added=added, modified=modified, removed=removed)
