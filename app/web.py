from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.log import get_logger
from app.features.auth.web_router import router as auth_web_router
from app.features.clients.web_router import router as clients_web_router
from app.features.eav.web_router import router as eav_web_router
from app.features.finances.web_router import router as finances_web_router
from app.features.home.web_router import router as home_router
from app.features.legal.web_router import router as legal_web_router
from app.features.orders.web_router import router as orders_web_router
from app.features.orgs.web_router import router as orgs_web_router
from app.features.products.web_router import router as products_web_router
from app.features.receipts.web_router import router as receipts_web_router
from app.shared.exceptions import AppHttpException
from app.shared.feature_flags import require_web_routers
from app.shared.i18n import i18n
from app.shared.templates import templates

logger = get_logger(__name__)


# Registering all routers and handlers
def register_web_routers(app: FastAPI) -> None:  # noqa: C901
    """Register HTML web routers, static files, and template-based error handlers.

    Every legacy HTML route is gated by ``require_web_routers``: when
    ``settings.web_routers_enabled`` is False they respond 410 Gone.
    """

    # Static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Landing pages (no auth required, at root /)
    app.include_router(home_router, dependencies=[Depends(require_web_routers)])
    app.include_router(legal_web_router, dependencies=[Depends(require_web_routers)])

    # CRM web routes under /app/
    app.include_router(
        auth_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        orgs_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        clients_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        products_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        orders_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        receipts_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        eav_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )
    app.include_router(
        finances_web_router, prefix="/app", dependencies=[Depends(require_web_routers)]
    )

    # /app redirect
    @app.get(
        "/app", include_in_schema=False, dependencies=[Depends(require_web_routers)]
    )
    @app.get(
        "/app/", include_in_schema=False, dependencies=[Depends(require_web_routers)]
    )
    async def app_redirect():
        return RedirectResponse(url="/app/orgs/select")

    # Language switcher
    @app.get("/lang/{lang}", dependencies=[Depends(require_web_routers)])
    async def set_language(lang: str, request: Request):
        if lang in i18n.supported_langs():
            response = RedirectResponse(
                url=request.headers.get("referer", "/"), status_code=302
            )
            response.set_cookie(key="lang", value=lang)

            return response

        return RedirectResponse(url="/", status_code=302)

    # Error handlers with HTML templates
    @app.exception_handler(StarletteHTTPException)
    async def web_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )

        template_map = {
            status.HTTP_404_NOT_FOUND: "errors/404.html",
            status.HTTP_403_FORBIDDEN: "errors/403.html",
            status.HTTP_400_BAD_REQUEST: "errors/400.html",
        }
        template = template_map.get(exc.status_code)

        if template:
            return templates.TemplateResponse(
                request, template, status_code=exc.status_code
            )

        if exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            return templates.TemplateResponse(
                request, "errors/500.html", status_code=500
            )

        return templates.TemplateResponse(
            request, "errors/404.html", status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def web_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = []

        for err in exc.errors():
            field = ".".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Invalid value")

            if request.url.path.startswith("/api/"):
                errors.append({"field": field, "message": msg})
            else:
                errors.append(f"{field}: {msg}")

        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=422, content={"detail": errors})

        return templates.TemplateResponse(
            request,
            "errors/400.html",
            status_code=422,
            context={
                "detail": "; ".join(
                    e if isinstance(e, str) else e.get("message", "") for e in errors
                )
            },
        )

    @app.exception_handler(AppHttpException)
    async def web_app_http_exception_handler(request: Request, exc: AppHttpException):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message, "code": exc.code},
            )

        template = {
            404: "errors/404.html",
            403: "errors/403.html",
            400: "errors/400.html",
        }.get(exc.status_code)

        if template:
            return templates.TemplateResponse(
                request,
                template,
                status_code=exc.status_code,
                context={"detail": exc.message},
            )

        return templates.TemplateResponse(
            request, "errors/500.html", status_code=exc.status_code
        )

    @app.exception_handler(IntegrityError)
    async def web_integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning(
            "db_integrity_error",
            path=request.url.path,
            method=request.method,
            error=str(exc.orig) if exc.orig else type(exc).__name__,
        )
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=409, content={"detail": "Conflict"})

        return JSONResponse(status_code=409, content={"detail": "Conflict"})

    @app.exception_handler(Exception)
    async def web_internal_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
        )
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

        return templates.TemplateResponse(request, "errors/500.html", status_code=500)
