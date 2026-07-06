"""Dependency-injection composition root.

No DI framework (architecture.md §3.7). This module is the single place the
object graph is built: settings -> engine/session factory -> repositories ->
domain services -> application services. Routers receive application
services through thin FastAPI ``Depends`` providers defined here; tests
build the same graph with in-memory fakes.

Implemented in Phase 2 — see tasks.md.
"""
