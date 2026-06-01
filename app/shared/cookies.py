"""Shared cookie flags for auth cookies (access/refresh).

Central place so API router and RefreshTokenMiddleware stay in sync
(httponly, samesite=lax, path=/, secure from settings, TTL per cookie).
"""

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE_MAX_AGE = 60 * 60  # 1 hour - matches access token TTL
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * settings.refresh_token_expire_days


def cookie_kwargs() -> dict:
    """Flags shared by every auth cookie (TTL is per cookie: access/refresh differ)."""

    return {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": settings.cookie_secure,
    }


COOKIE_KWARGS = cookie_kwargs()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=ACCESS_COOKIE_MAX_AGE,
        **COOKIE_KWARGS,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        **COOKIE_KWARGS,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
