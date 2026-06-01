import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.shared.i18n import i18n

logger = structlog.get_logger(__name__)

_SUPPORTED = set(i18n.supported_langs())


class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        lang = request.cookies.get("lang", "")

        if lang not in _SUPPORTED:
            accept = request.headers.get("accept-language", "")
            lang = "pl"

            for part in accept.split(","):
                code = part.strip().split(";")[0][:2].lower()

                if code in _SUPPORTED:
                    lang = code

                    break

        request.state.lang = lang

        return await call_next(request)
