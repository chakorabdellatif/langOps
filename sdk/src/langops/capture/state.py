"""Safe state serialization.

Serializes arbitrary LangGraph state: fallback repr for non-JSON values,
depth limits, and size capping at LangOpsConfig.max_payload_bytes with a
``langops.truncated`` marker.

Implemented in Phase 3 — see tasks.md.
"""
