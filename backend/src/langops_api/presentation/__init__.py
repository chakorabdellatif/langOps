"""Presentation layer — HTTP only.

Routers do exactly three things: validate input via Pydantic, call one
application service, shape the response. No business logic, ever. Never
imports infrastructure (CI-enforced). Route map: architecture.md §3.4.
"""
