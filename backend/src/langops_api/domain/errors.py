"""Domain error hierarchy. Presentation maps these to HTTP responses."""


class LangOpsError(Exception):
    """Base for all LangOps errors."""

    code = "internal_error"

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(LangOpsError):
    code = "not_found"


class ExecutionNotFound(NotFoundError):
    code = "execution_not_found"


class NodeExecutionNotFound(NotFoundError):
    code = "node_execution_not_found"


class ThreadNotFound(NotFoundError):
    code = "thread_not_found"


class InvalidTelemetry(LangOpsError):
    """Malformed OTLP payload — maps to HTTP 400, never 500."""

    code = "invalid_telemetry"


class RequestTooLarge(LangOpsError):
    """OTLP payload exceeds the configured size limit — maps to HTTP 413."""

    code = "request_too_large"
