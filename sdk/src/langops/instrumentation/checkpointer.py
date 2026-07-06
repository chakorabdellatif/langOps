"""Checkpointer wrapper — authoritative state snapshots.

A decorator object implementing BaseCheckpointSaver (composition, not
subclassing) that delegates to the original checkpointer. Every put() emits a
state snapshot event with checkpoint id, parent checkpoint id, channel
values, and a structural diff against the previously seen state. Graphs
without a checkpointer degrade gracefully to callback-derived state capture.

Implemented in Phase 3 — see tasks.md and architecture.md §5.3(3).
"""
