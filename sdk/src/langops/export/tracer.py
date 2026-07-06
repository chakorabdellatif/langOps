"""OTel TracerProvider setup.

A dedicated TracerProvider (never hijacking the user's global provider) with
resource attributes: service.name, langops.sdk.version, langops.project.

Implemented in Phase 3 — see tasks.md and architecture.md §5.4.
"""
