"""Runtime feature gates (feature flags).

CSV routes are always registered (so literal paths are not intercepted by
parameterized routes such as /{client_id}), but access is gated here:
when settings.feature_csv=False, any request to a CSV endpoint returns 404.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import settings


def require_feature_csv() -> None:
    if not settings.feature_csv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature is disabled",
        )


RequireFeatureCsv = Annotated[None, Depends(require_feature_csv)]


def require_web_routers() -> None:
    if not settings.web_routers_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Deprecated server-rendered routes are disabled. "
                "Use the SPA frontend and the JSON API instead."
            ),
        )


RequireWebRouters = Annotated[None, Depends(require_web_routers)]
