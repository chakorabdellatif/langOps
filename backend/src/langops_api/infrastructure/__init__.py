"""Infrastructure layer — implements domain interfaces (dependency inversion).

SQLAlchemy repositories satisfy the Protocols in domain/repositories/;
ORM models live here, separate from domain entities. Also: settings,
Redis cache/pub-sub adapters, OTLP parsing.
"""
