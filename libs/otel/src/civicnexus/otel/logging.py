"""Structured JSON logging in Cloud Logging's native field shape.

Cloud Logging promotes ``severity``, ``time``, and ``message`` from JSON lines
on stdout into first-class log fields, so plain stdout emission is the whole
transport — no client library needed.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_SEVERITY = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}

_RESERVED_ATTRS = frozenset(vars(logging.makeLogRecord({})))


class JsonFormatter(logging.Formatter):
    """Formats records as single-line JSON with Cloud Logging field names."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "severity": _SEVERITY.get(record.levelno, "DEFAULT"),
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "message": record.getMessage(),
            "service": self._service,
            "logger": record.name,
        }
        for key, value in vars(record).items():
            # Caller extras must never clobber the canonical output fields
            # (severity/time/message/service/logger) — drop shadowing keys.
            if key in _RESERVED_ATTRS or key.startswith("_") or key in entry:
                continue
            entry[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def get_logger(service: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger for ``service`` that emits structured JSON to stdout.

    Idempotent per service name: repeated calls return the same configured
    logger without stacking handlers.
    """
    logger = logging.getLogger(f"civicnexus.{service}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter(service))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
