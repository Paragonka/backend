import logging
import sys

import structlog


def setup_logging() -> None:
    # Local import avoids a circular import at module load time
    # (config imports several app modules transitively).
    from app.core.config import settings

    log_level_name = getattr(settings, "log_level", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    is_prod = settings.environment == "production"

    # Route both structlog (via LoggerFactory) and plain `logging` calls
    # (e.g. app/shared/s3.py) through one handler/sink and one level, so the
    # configured LOG_LEVEL is actually honoured everywhere.
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=log_level,
        )
    else:
        root.setLevel(log_level)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_prod:
        processors: list[structlog.typing.Processor] = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                force_colors=True,
                sort_keys=False,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
