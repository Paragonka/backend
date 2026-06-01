"""Thin logging helpers shared across the application.

Centralises logger creation and request-context binding so that every log
line emitted during a request automatically carries the acting user and the
tenant (org) it belongs to - the backbone of a multi-tenant audit trail.
"""

import structlog


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def bind_request_context(
    *,
    user_id: str | None = None,
    org_id: str | None = None,
) -> None:
    """Bind the acting user and tenant to structlog contextvars.

    Contextvars are request-scoped in ASGI: values set here are visible to every
    subsequent log call within the same request task and reset automatically
    afterwards (no manual clearing required).
    """

    bindings: dict[str, str] = {}

    if user_id is not None:
        bindings["user_id"] = str(user_id)

    if org_id is not None:
        bindings["org_id"] = str(org_id)

    if bindings:
        structlog.contextvars.bind_contextvars(**bindings)
