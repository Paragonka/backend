import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.core.security import decode_refresh_token
from app.shared.cookies import (
    ACCESS_COOKIE_MAX_AGE,
    COOKIE_KWARGS,
    REFRESH_COOKIE_MAX_AGE,
    clear_auth_cookies,
)

logger = structlog.get_logger(__name__)

# Factory for DB sessions used by middleware.
# Overridable for tests via set_session_factory.
_session_factory = None


def set_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


def _get_session_factory():
    if _session_factory is not None:
        return _session_factory

    from app.core.database import AsyncSessionLocal

    return AsyncSessionLocal


def get_db_session_factory():
    """Public accessor for other middlewares needing the overridable factory."""

    return _get_session_factory()


class RefreshTokenMiddleware(BaseHTTPMiddleware):
    """Silently refresh expired access_token using refresh_token cookie.

    Web: intercepts 401, refreshes if possible, redirects back or to login.
    API: passes 401 through (frontend handles refresh itself).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        if response.status_code != 401:
            return response

        path = str(request.url.path)

        # Let API clients handle 401 themselves (mobile, SPA, etc.)
        if path.startswith("/api/"):
            return response

        # Ignore auth/login pages to avoid redirect loops
        if path.startswith("/app/auth/"):
            return response

        refresh_token = request.cookies.get("refresh_token")

        if not refresh_token:
            logger.info("refresh_missing", path=path)

            return RedirectResponse(url="/app/auth/login", status_code=302)

        payload = decode_refresh_token(refresh_token)

        if not payload:
            logger.info("refresh_invalid", path=path)
            resp = RedirectResponse(url="/app/auth/login", status_code=302)
            clear_auth_cookies(resp)

            return resp

        # Use AuthService with session factory to handle rotation via DB
        try:
            from app.core.uow import AppUnitOfWork
            from app.features.auth.service import AuthService

            factory = _get_session_factory()
            service = AuthService(AppUnitOfWork(factory))
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")
            result = await service.refresh_tokens(refresh_token, ip, ua)

            if result:
                user, new_access, new_refresh = result
                logger.info("token_refreshed", path=path, user_id=str(user.id))
                redirect = RedirectResponse(url=str(request.url), status_code=302)
                redirect.set_cookie(
                    key="access_token",
                    value=new_access,
                    max_age=ACCESS_COOKIE_MAX_AGE,
                    **COOKIE_KWARGS,
                )
                redirect.set_cookie(
                    key="refresh_token",
                    value=new_refresh,
                    max_age=REFRESH_COOKIE_MAX_AGE,
                    **COOKIE_KWARGS,
                )

                return redirect

            logger.info("refresh_reuse_or_invalid", path=path)
            resp = RedirectResponse(url="/app/auth/login", status_code=302)
            clear_auth_cookies(resp)

            return resp
        except Exception as e:
            logger.warning("refresh_middleware_error", error=str(e), path=path)
            # fallback to simple decode attempt? treat as invalid
            resp = RedirectResponse(url="/app/auth/login", status_code=302)
            clear_auth_cookies(resp)

            return resp
