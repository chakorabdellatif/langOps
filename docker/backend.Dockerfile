# langops-api — FastAPI backend
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY backend/pyproject.toml backend/README.md ./
RUN pip install .

# Then the source and migrations.
COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
RUN pip install --no-deps .

EXPOSE 8000

# Apply migrations, then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn langops_api.main:app --host 0.0.0.0 --port 8000"]
