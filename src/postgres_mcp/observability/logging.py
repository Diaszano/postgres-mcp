"""Context-propagated request tracing and sanitized logging helpers."""

import contextvars
from contextlib import contextmanager
from typing import Iterator

_OPERATION_ID_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar("operation_id", default=None)


def get_operation_id() -> str | None:
    """Retrieve the current operation/request ID from contextvars."""
    return _OPERATION_ID_CTX.get()


@contextmanager
def operation_context(request_id: str) -> Iterator[str]:
    """Scope execution with a specific request/operation ID."""
    token = _OPERATION_ID_CTX.set(request_id)
    try:
        yield request_id
    finally:
        _OPERATION_ID_CTX.reset(token)
