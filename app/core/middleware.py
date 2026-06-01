import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from uuid_extensions import uuid7

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid7())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.monotonic()
        method = request.method
        path = request.url.path

        logger.info("request_start", method=method, path=path)

        try:
            response = await call_next(request)
            elapsed = time.monotonic() - start
            status_code = response.status_code

            if status_code >= 500:
                logger.error(
                    "request_server_error",
                    method=method,
                    path=path,
                    status_code=status_code,
                    elapsed_ms=round(elapsed * 1000),
                )
            else:
                logger.info(
                    "request_complete",
                    method=method,
                    path=path,
                    status_code=status_code,
                    elapsed_ms=round(elapsed * 1000),
                )

            response.headers["X-Request-ID"] = request_id

            return response

        except Exception:
            # logger.exception captures the traceback automatically (BoundLogger).
            # user_id / org_id are merged from structlog contextvars if bound
            # by the auth dependencies during this request.
            elapsed = time.monotonic() - start
            logger.exception(
                "request_failed",
                method=method,
                path=path,
                elapsed_ms=round(elapsed * 1000),
            )

            raise
        finally:
            structlog.contextvars.clear_contextvars()
