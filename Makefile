# LangOps development entrypoints.
# Requires: docker compose v2, Python 3.12 + uv (or pip), Node 20+.

.PHONY: up down reset logs e2e lint test fmt migrate \
        lint-sdk lint-backend lint-dashboard \
        test-sdk test-backend test-dashboard

## ── Stack ────────────────────────────────────────────────────────────

up:            ## Build and start the full local stack
	docker compose up --build

down:          ## Stop the stack
	docker compose down

reset:         ## Stop the stack and wipe all data (Postgres volume)
	docker compose down -v

logs:          ## Tail logs from all services
	docker compose logs -f

e2e:           ## Full pipeline smoke test (compose up, run example, verify)
	bash scripts/e2e-smoke.sh

## ── Quality gates (aggregate) ────────────────────────────────────────

lint: lint-sdk lint-backend lint-dashboard

test: test-sdk test-backend test-dashboard

## ── SDK ──────────────────────────────────────────────────────────────

lint-sdk:
	cd sdk && ruff check src tests && ruff format --check src tests && mypy src

test-sdk:
	cd sdk && pytest

## ── Backend ──────────────────────────────────────────────────────────

lint-backend:
	cd backend && ruff check src tests && ruff format --check src tests && mypy src && lint-imports

test-backend:
	cd backend && pytest

migrate:       ## Apply database migrations against the running Postgres
	cd backend && alembic upgrade head

## ── Dashboard ────────────────────────────────────────────────────────

lint-dashboard:
	cd dashboard && npm run lint && npm run typecheck

test-dashboard:
	cd dashboard && npm test
