# langops-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The package uses a src/ layout, so the source must be present for the build.
COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src
RUN pip install .

# Migrations run at container start (not baked into the image).
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic

EXPOSE 8000

# Apply migrations (idempotent), then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn langops_api.main:app --host 0.0.0.0 --port 8000"]
