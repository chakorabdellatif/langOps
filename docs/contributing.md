# Contributing to LangOps

Start with the [Architecture Design Document](architecture.md) — it is the
implementation blueprint. The phased build plan lives in [`tasks.md`](../tasks.md).

## Setup

```bash
cp .env.example .env
make up          # full stack via Docker Compose
make lint        # ruff + mypy + eslint across all packages
make test        # all test suites
```

Install pre-commit hooks once: `pre-commit install`.

## Ground rules

- **Layering** (backend): `presentation → application → domain ← infrastructure`.
  Enforced by import-linter; the domain imports no frameworks.
- **Semantic conventions**: never invent an OTel attribute inline — add it to
  [`semantic-conventions.md`](semantic-conventions.md) and the mirrored
  constants first.
- **Commits**: Conventional Commits with scopes
  `sdk | api | dashboard | collector | docker | docs`.
- **Decisions**: significant choices get an ADR in [`docs/adr/`](adr/).

See §9 of the architecture document for the full conventions (naming,
logging, errors, testing).
