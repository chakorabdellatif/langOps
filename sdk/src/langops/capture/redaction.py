"""User-pluggable payload scrubbing.

The redaction hook from LangOpsConfig is applied to every captured payload
*before* it reaches the exporter — secrets never leave the process.

Implemented in Phase 3 — see tasks.md.
"""
