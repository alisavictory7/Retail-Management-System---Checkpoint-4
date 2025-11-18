from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from flask import Flask, g, has_request_context, request, session

from src.config import Config


class RequestContextFilter(logging.Filter):
    """Inject Flask request context information into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if has_request_context():
            record.request_id = getattr(g, "request_id", None)
            record.path = request.path
            record.method = request.method
            record.user_id = session.get("user_id")
        else:
            record.request_id = None
            record.path = None
            record.method = None
            record.user_id = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "path": getattr(record, "path", None),
            "method": getattr(record, "method", None),
            "user_id": getattr(record, "user_id", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(app: Flask) -> None:
    """Configure global logging once, respecting Config toggles."""

    if not Config.STRUCTURED_LOGS_ENABLED:
        app.logger.setLevel(Config.LOG_LEVEL)
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(Config.LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())

    # Remove existing handlers to avoid duplicate logs when reloading
    root_logger.handlers = [handler]
    app.logger.handlers = [handler]

    app.logger.debug("Structured logging configured.")


def ensure_request_id() -> str:
    """Return the active request id, generating one if needed."""
    if getattr(g, "request_id", None):
        return g.request_id
    incoming = request.headers.get(Config.REQUEST_ID_HEADER)
    g.request_id = incoming or str(uuid4())
    return g.request_id

