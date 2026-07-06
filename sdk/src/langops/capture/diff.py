"""Structural state diffing.

Computes {added, modified, removed} between two JSON-like states. The
backend recomputes/validates diffs server-side so the dashboard never
depends on the SDK version.

Implemented in Phase 3 — see tasks.md.
"""
