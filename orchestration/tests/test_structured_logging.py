"""Structured JSON logging (observability.md telemetry slice).

Covers the JSON formatter contract and the request-logging middleware:
one structured event per request carrying the designed correlation
fields (method, path, status, duration, correlation id, user id).
"""

from __future__ import annotations

import json
import logging
import uuid

import httpx
import pytest

from orchestration.config import Settings
from orchestration.main import create_app

CORR = "11111111-1111-4111-8111-111111111111"
USER = "12345678-1234-4123-8123-123456789abc"

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


def _app_client() -> httpx.AsyncClient:
    settings = Settings(
        db_dsn="postgresql://x",
        story_url="http://story:8080/mcp",
        artifact_url="http://artifact:8080/mcp",
        report_url="http://report:8080/mcp",
        bucket="artifacts-local",
        business_url="http://business:8080",
        engineering_url="http://engineering:8080",
        synthesis_url="http://synthesis:8080",
        facilitator_url="http://facilitator:8080",
        gcs_public_url="https://gcs.invalid",
    )
    app = create_app(settings=settings)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    )


def test_formatter_emits_json_with_severity_service_and_extras():
    from orchestration.structured_logging import JsonFormatter

    formatter = JsonFormatter(service="orchestration")
    record = logging.LogRecord(
        name=REQUEST_LOGGER,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.correlation_id = CORR

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "request"
    assert payload["severity"] == "INFO"
    assert payload["service"] == "orchestration"
    assert payload["correlation_id"] == CORR


async def test_request_emits_structured_event_with_correlation_fields(capture):
    async with _app_client() as client:
        response = await client.get(
            "/api/v1/does-not-exist",
            headers={"X-Correlation-Id": CORR, "X-User-Id": USER},
        )
    assert response.status_code == 404

    assert len(capture.records) == 1
    record = capture.records[0]
    assert record.getMessage() == "request"
    assert record.method == "GET"
    assert record.path == "/api/v1/does-not-exist"
    assert record.status == 404
    assert record.duration_ms >= 0
    assert record.correlation_id == CORR
    assert record.user_id == USER


async def test_request_without_user_header_logs_null_user(capture):
    async with _app_client() as client:
        await client.get("/api/v1/does-not-exist")

    record = capture.records[0]
    # Correlation id is minted when not supplied (never absent).
    uuid.UUID(record.correlation_id)
    assert record.user_id is None
