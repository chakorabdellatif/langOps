"""Domain layer — entities, value objects, repository Protocols, pure services.

Hard rule (CI-enforced): this package imports nothing but the standard
library. No FastAPI, no SQLAlchemy, no Pydantic. The domain never knows
Postgres exists.
"""
