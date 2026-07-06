# Database Reference

The authoritative schema design lives in
[architecture.md §4](architecture.md#4-database-design-postgresql):
principles (UUIDv7 PKs, JSONB payloads vs typed query columns,
`project_id` everywhere), full table definitions, indexes, and
relationships.

This file will hold the generated ERD and any schema notes that emerge
during implementation (Phase 2 of [`tasks.md`](../tasks.md)). Migrations are
Alembic-managed under `backend/alembic/versions/`.
