from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.i18n_middleware import I18nMiddleware
from app.core.log import get_logger
from app.core.logger import setup_logging
from app.core.middleware import LoggingMiddleware
from app.core.refresh_middleware import RefreshTokenMiddleware
from app.features.auth.api_router import router as auth_api_router
from app.features.clients.api_router import router as clients_api_router
from app.features.eav.api_router import router as eav_api_router
from app.features.finances.api_router import router as finances_api_router
from app.features.legal.api_router import router as legal_api_router
from app.features.media.api_router import router as media_api_router
from app.features.orders.api_router import router as orders_api_router
from app.features.orgs.api_router import router as orgs_api_router
from app.features.products.api_router import router as products_api_router
from app.features.receipts.api_router import router as receipts_api_router
from app.shared.exceptions import AppHttpException

setup_logging()

logger = get_logger(__name__)

app = FastAPI(title="Paragonka CRM")

# Middleware - RefreshToken needed for all modes (API auth)
app.add_middleware(RefreshTokenMiddleware)

# Request logging: active in BOTH web and API-only modes. The I18nMiddleware is
# web-only, but request/audit logging must never be skipped for API traffic.
app.add_middleware(LoggingMiddleware)

# Web UI layer and web-only middleware
if settings.web_enabled:
    from app.web import register_web_routers

    app.add_middleware(I18nMiddleware)

    # Web handlers are comprehensive (JSON for API paths, HTML for web paths)
    register_web_routers(app)
else:
    # API-only mode: JSON error handlers

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = []

        for err in exc.errors():
            field = ".".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            errors.append({"field": field, "message": msg})

        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(AppHttpException)
    async def app_http_exception_handler(request: Request, exc: AppHttpException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        # A DB constraint violation is a signal of bad input or a race; log it
        # for diagnosis but do not leak the raw SQL/constraint to the client.
        logger.warning(
            "db_integrity_error",
            path=request.url.path,
            method=request.method,
            error=str(exc.orig) if exc.orig else type(exc).__name__,
        )
        return JSONResponse(status_code=409, content={"detail": "Conflict"})

    @app.exception_handler(Exception)
    async def internal_exception_handler(request: Request, exc: Exception):
        # Critical: an unhandled exception must always be logged with the
        # traceback - the previous handler silently returned 500.
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )


# CORS. Added LAST via add_middleware -> in Starlette this is the outermost
# layer: preflight OPTIONS gets a response before Refresh/Consent/I18n/Logging.
# allow_origins comes from settings.cors_origins (env CORS_ORIGINS); "*" together
# with allow_credentials=True is forbidden.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API routes
app.include_router(auth_api_router)
app.include_router(orgs_api_router)
app.include_router(clients_api_router)
app.include_router(products_api_router)
app.include_router(eav_api_router)
app.include_router(orders_api_router)
app.include_router(media_api_router)
app.include_router(receipts_api_router)
app.include_router(finances_api_router)
# Legal / consent API - always registered, regardless of web_enabled
app.include_router(legal_api_router)


@app.get("/health")
async def read_root():
    return {"status": "OK"}
