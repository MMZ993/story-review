"""Structured JSON logging for the webui proxy.

Emits one JSON object per log line on stdout so Cloud Run's captured
output becomes structured Cloud Logging entries (observability.md
"Telemetry and tracing"): every event carries ``message``,
``severity``, ``service``, plus any correlation fields the call site
attaches via ``extra``. Mirrors the orchestration module byte-for-byte
in behavior; kept duplicated rather than shared because the units
deploy as independent images (duplication over obscuring abstraction).
"""

from __future__ import annotations

import json
import logging
import sys

#: Root logger for this service's structured events (children append
#: their scope, e.g. ``storyreview.request``).
LOGGER_NAME = "storyreview"

#: LogRecord attributes owned by the logging machinery — everything
#: else in ``record.__dict__`` is an ``extra`` correlation field.
_RESERVED = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relative_created",
        "thread", "threadName", "processName", "process", "taskName",
        "message", "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Serialize a record plus its extra fields as one JSON line.

    Args: service — the emitting service's name (``service`` field).
    """

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "message": record.getMessage(),
            "severity": record.levelname,
            "service": self.service,
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _RESERVED and not key.startswith("_")
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service: str) -> None:
    """Attach the JSON stdout handler to ``storyreview`` once.

    Idempotent: repeated calls (per app factory invocation in tests,
    multiple workers) never stack handlers.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if any(
        isinstance(getattr(h, "formatter", None), JsonFormatter)
        for h in logger.handlers
    ):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
