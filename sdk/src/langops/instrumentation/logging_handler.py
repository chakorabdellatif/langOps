"""Bridge stdlib ``logging`` records into the active trace (v0.2, opt-in).

When ``LangOpsConfig(capture_logs=True)``, a single handler is attached to the
root logger. Each record emitted *during* an instrumented run becomes a
``langops.log`` span event on the node (or execution) span that is currently
executing; records emitted outside a run are ignored (they have nowhere to
attach). Records from the ``langops`` logger itself are tagged source ``sdk``.

Like every capture path, this is fault-isolated: a failure to record a log can
never propagate into the host application's logging call.
"""

from __future__ import annotations

import logging

from langops import semconv
from langops.config import LangOpsConfig
from langops.instrumentation.runtime import add_payload_event, current_run

_LEVEL_TO_NAME = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


class LangOpsLogHandler(logging.Handler):
    """A logging handler that records log lines onto the active LangOps span."""

    def __init__(self, config: LangOpsConfig) -> None:
        super().__init__()
        self._config = config

    def emit(self, record: logging.LogRecord) -> None:
        try:
            run = current_run.get()
            if run is None:
                return  # no active execution — nothing to attach to
            level = _LEVEL_TO_NAME.get(record.levelno, record.levelname.lower())
            source = (
                semconv.LogSource.SDK
                if record.name.split(".", 1)[0] == "langops"
                else semconv.LogSource.APP
            )
            # One event carrying both the log metadata and the (redacted,
            # size-capped) message payload.
            add_payload_event(
                run.target_span,
                semconv.EVENT_LOG,
                {"message": record.getMessage()},
                self._config,
                extra_attributes={
                    semconv.LOG_LEVEL: level,
                    semconv.LOG_LOGGER: record.name,
                    semconv.LOG_SOURCE: source,
                },
            )
        except Exception:  # noqa: BLE001 — logging must never break the host app
            return


_installed: LangOpsLogHandler | None = None


def install_log_capture(config: LangOpsConfig) -> None:
    """Attach the log handler to the root logger once (idempotent)."""
    global _installed
    if _installed is not None:
        return
    handler = LangOpsLogHandler(config)
    handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(handler)
    _installed = handler
