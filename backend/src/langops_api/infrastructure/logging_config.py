"""Structured JSON logging via structlog.

Routes both structlog and stdlib logs (uvicorn, sqlalchemy) through one JSON
renderer, with `contextvars` merged in — so any log emitted during ingest
carries the correlation fields bound by `bind_ingest_context`
(trace_id / execution_id / thread_id / checkpoint_id).
"""

from __future__ import annotations

import logging
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

_SHARED: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[*_SHARED, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def bind_ingest_context(
    *,
    trace_id: str | None = None,
    execution_id: str | None = None,
    thread_id: str | None = None,
    checkpoint_id: str | None = None,
) -> None:
    fields = {
        "trace_id": trace_id,
        "execution_id": execution_id,
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id,
    }
    bind_contextvars(**{k: v for k, v in fields.items() if v is not None})


def clear_ingest_context() -> None:
    clear_contextvars()
