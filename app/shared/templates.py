from pathlib import Path
from typing import Any, cast

import structlog
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache

from app.core.config import settings
from app.shared.i18n import i18n

logger = structlog.get_logger(__name__)

_cache_dir = Path(".jinja_cache")
_cache_dir.mkdir(exist_ok=True)

templates = Jinja2Templates(directory="templates")
templates.env.globals["feature_csv"] = settings.feature_csv
templates.env.bytecode_cache = FileSystemBytecodeCache(
    directory=str(_cache_dir),
    pattern="__jinja2_%s.cache",
)

_tailwind_path = Path("static/tailwind.css")


def format_time(value: str | None) -> str:
    if not value or len(value) < 16:
        return value or ""

    return value[11:16]


_daisyui_path = Path("static/daisyui.css")

if _tailwind_path.exists():
    mtime = int(_tailwind_path.stat().st_mtime)
    templates.env.globals["tailwind_css_url"] = f"/static/tailwind.css?v={mtime}"
else:
    templates.env.globals["tailwind_css_url"] = None

if _daisyui_path.exists():
    mtime = int(_daisyui_path.stat().st_mtime)
    templates.env.globals["daisyui_css_url"] = f"/static/daisyui.css?v={mtime}"
else:
    templates.env.globals["daisyui_css_url"] = None

templates.env.filters["format_time"] = format_time

# Monkey-patch TemplateResponse to inject i18n context
_original_response = Jinja2Templates.TemplateResponse


def _patched_response(
    self: Any,
    request: Any,
    name: Any,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
    headers: Any = None,
    media_type: Any = None,
    background: Any = None,
) -> Any:
    if context is None:
        context = {}

    lang = getattr(request.state, "lang", "pl")
    context.setdefault("current_lang", lang)
    context.setdefault("_", lambda key: i18n.gettext(key, lang))

    return _original_response(
        self,
        request,
        name,
        context=context,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        background=background,
    )


Jinja2Templates.TemplateResponse = cast(Any, _patched_response)
