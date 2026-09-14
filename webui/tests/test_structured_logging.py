"""Structured JSON logging for the webui proxy (observability.md slice).

Covers the shared formatter contract and the proxy request log: one
structured event per /api request with the upstream correlation id;
static-shell requests are not logged.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest

REQUEST_LOGGER = "storyreview.request"


class CaptureHandler(logging.Handler):
    """Collect records so assertions can run against attributes."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def capture():
    handler = CaptureHandler()
    logger = logging.getLogger(REQUEST_LOGGER)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


def test_formatter_emits_json_with_severity_service_and_extras():
    from webui.structured_logging import JsonFormatter

    formatter = JsonFormatter(service="webui")
    record = logging.LogRecord(
        name=REQUEST_LOGGER,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.status = 503

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "request"
    assert payload["severity"] == "INFO"
    assert payload["service"] == "webui"
    assert payload["status"] == 503


def test_proxied_request_emits_structured_event(client, upstream, capture):
    upstream["handler"] = lambda request: httpx.Response(
        200, json={"stories": []}, headers={"X-Correlation-Id": "c-1"}
    )
    response = client.get("/api/v1/stories")

    assert response.status_code == 200
    assert len(capture.records) == 1
    record = capture.records[0]
    assert record.getMessage() == "request"
    assert record.method == "GET"
    assert record.path == "/api/v1/stories"
    assert record.status == 200
    assert record.duration_ms >= 0
    assert record.correlation_id == "c-1"


def test_static_shell_requests_are_not_logged(client, capture):
    response = client.get("/")

    assert response.status_code == 200
    assert capture.records == []
