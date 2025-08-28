"""
Logging configuration utilities for the FastAPI application.

Provides:
- configure_logging: set log level from env, and select JSON or human-readable format.
- get_logger: convenience accessor to the application logger.

Behavior:
- If APP_ENV is "production", use JSON logs.
- Otherwise, use a concise human formatter with colors (if supported).
- LOG_LEVEL environment variable controls level (default: INFO).

Environment variables are read via Settings from config.py when possible.
"""

import json
import logging
import os
from typing import Optional

from .config import get_settings


class JsonFormatter(logging.Formatter):
    """Basic JSON log formatter suitable for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
        }
        # Attach extra fields if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "path"):
            payload["path"] = getattr(record, "path")
        if hasattr(record, "method"):
            payload["method"] = getattr(record, "method")
        if hasattr(record, "status_code"):
            payload["status_code"] = getattr(record, "status_code")
        return json.dumps(payload, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Human-friendly formatter for development."""

    default_fmt = "[%(levelname)s] %(asctime)s - %(name)s - %(message)s"
    default_datefmt = "%H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.default_fmt, datefmt=self.default_datefmt)


# PUBLIC_INTERFACE
def configure_logging(force: bool = False) -> None:
    """
    Configure global logging handlers and formatters.

    - Sets root logger level from LOG_LEVEL env var or Settings.APP_DEBUG (DEBUG if true else INFO).
    - If APP_ENV == 'production', uses JSON logs; otherwise uses human-readable logs.
    - Idempotent unless force=True.
    """
    settings = None
    try:
        settings = get_settings()
    except Exception:
        # If settings cannot be loaded (e.g., during early boot), fall back to env only
        pass

    app_env = (settings.APP_ENV if settings else os.getenv("APP_ENV", "development")).lower()
    # Determine log level
    env_level = os.getenv("LOG_LEVEL")
    if env_level:
        level_name = env_level.upper()
    else:
        level_name = "DEBUG" if (settings.APP_DEBUG if settings else os.getenv("APP_DEBUG", "true").lower() in ("1", "true", "yes")) else "INFO"

    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    if root_logger.handlers and not force:
        # already configured; just ensure level is correct
        root_logger.setLevel(level)
        return

    # Clear existing handlers if any
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler()
    if app_env == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Silence overly chatty libraries a bit in dev/prod
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# PUBLIC_INTERFACE
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a module or root logger after ensuring configuration."""
    configure_logging()  # safe to call repeatedly
    return logging.getLogger(name if name else "app")
