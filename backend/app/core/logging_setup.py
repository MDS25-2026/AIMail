"""One root handler for the backend and the agent, every line tagged with its request id.

Without it nothing configured logging at all, so every logger.info in app/ went to Python's
last-resort handler, which drops everything below WARNING.
"""

import json
import logging
from contextvars import ContextVar

from app.core.config import LogFormat, get_settings

request_id: ContextVar[str] = ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
DEFAULT_LEVEL = "INFO"
# Chatty at INFO (one line per HTTP call), and those lines would repeat what our own logs say.
QUIET_LOGGERS = ("httpx", "httpcore", "google_genai", "urllib3")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the same fields as the text format."""

    def format(self, record: logging.LogRecord) -> str:
        line = {"time": self.formatTime(record), "level": record.levelname,
                "request_id": getattr(record, "request_id", "-"), "logger": record.name,
                "message": record.getMessage()}
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def _formatter() -> logging.Formatter:
    return JsonFormatter() if get_settings().log_format == LogFormat.JSON else logging.Formatter(LOG_FORMAT)


def _level() -> int:
    """A mistyped LOG_LEVEL falls back to INFO rather than failing startup or going silent."""
    named = logging.getLevelNamesMapping().get((get_settings().log_level or DEFAULT_LEVEL).upper())
    return named if named is not None else logging.INFO


def configure_logging() -> None:
    """Idempotent: uvicorn --reload re-imports the app, and a second handler doubles every line."""
    root = logging.getLogger()
    if any(isinstance(f, RequestIdFilter) for h in root.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(_formatter())
    root.addHandler(handler)
    root.setLevel(_level())
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
