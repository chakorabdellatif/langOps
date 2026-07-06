"""Application layer — one class per use case.

Services are constructor-injected with repository Protocols and domain
services, return plain-dataclass DTOs, and contain no HTTP or persistence
concerns. Catalog: architecture.md §3.3.
"""
