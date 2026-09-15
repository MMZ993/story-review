"""Orchestration HTTP client with webui idempotency discipline (inc 1).

Drives the compose orchestration API exactly like the webui does: a v4
``x-user-id`` per evaluation run, a v4 ``Idempotency-Key`` minted and
"persisted" before each POST, and bounded same-key retry on retryable 503.
Any other status raises ``OrchestrationError`` carrying the status and
body so the case runner can fail the case with evidence.
"""

from __future__ import annotations

import time
import uuid
from typing import Protocol

import httpx

#: Bounded same-key retry after a retryable outcome (webui api.js pattern:
#: 5 attempts; SESSION_LOCKED waits the envelope's retry_after_seconds).
MAX_ATTEMPTS = 5
RETRY_BACKOFF_SECONDS = 2.0


class KeyStore(Protocol):
    """Where idempotency keys are recorded before the request is sent."""

    def set(self, scope: str, key: str) -> None: ...


class MemoryKeyStore:
    """In-memory key persistence (sufficient: one process, sequential turns)."""

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}

    def set(self, scope: str, key: str) -> None:
        self._keys[scope] = key


class OrchestrationError(Exception):
    """A non-retryable or exhausted HTTP outcome, with response evidence."""

    def __init__(self, operation: str, status: int, body: str):
        super().__init__(f"{operation} -> {status}: {body[:500]}")
        self.operation = operation
        self.status = status
        self.body = body


def _should_retry(status: int, code: str) -> bool:
    """Webui rule: any 503, or 409 SESSION_LOCKED, retries with the same key."""
    return status == 503 or (status == 409 and code == "SESSION_LOCKED")


def _error_envelope(response: httpx.Response) -> dict:
    """The error envelope as a dict, or {} for non-JSON bodies."""
    try:
        body = response.json()
    except ValueError:
        return {}
    return body.get("error", {}) if isinstance(body, dict) else {}


class OrchestrationClient:
    """Thin typed client over the compose orchestration API."""

    def __init__(
        self,
        transport: httpx.BaseTransport,
        base_url: str = "http://127.0.0.1:8130",
        user_id: str | None = None,
        key_store: KeyStore | None = None,
        sleep=time.sleep,
    ):
        self._client = httpx.Client(transport=transport, base_url=base_url, timeout=600.0)
        self.user_id = user_id or str(uuid.uuid4())
        self._keys = key_store or MemoryKeyStore()
        self._sleep = sleep

    # -- public API ---------------------------------------------------------

    def create_session(self, story_id: str, requested_formats: list[str]) -> dict:
        """Flow 1: create a session; returns the CreateSessionResponse JSON."""
        return self._post(
            "create-session",
            "/api/v1/sessions",
            {"story_id": story_id, "requested_formats": requested_formats},
            expected=201,
        )

    def post_turn(self, session_id: str, body: dict) -> dict:
        """Flow 2/3: one turn (message or po_accepted acceptance)."""
        return self._post(
            "post-turn",
            f"/api/v1/sessions/{session_id}/turns",
            body,
            expected=200,
        )

    def get_session(self, session_id: str) -> dict:
        """SessionDetail for restore probes (bounded 503 retry, no key needed
        — GET is safe and carries no idempotency semantics)."""
        last: httpx.Response | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = self._request("GET", f"/api/v1/sessions/{session_id}")
            if response.status_code == 200:
                return response.json()
            if response.status_code != 503 or attempt == MAX_ATTEMPTS:
                raise OrchestrationError(
                    "get-session", response.status_code, response.text
                )
            last = response
            self._sleep(RETRY_BACKOFF_SECONDS * attempt)
        assert last is not None  # pragma: no cover
        raise OrchestrationError("get-session", last.status_code, last.text)

    def close(self) -> None:
        self._client.close()

    # -- internals ----------------------------------------------------------

    def _post(self, operation: str, path: str, json_body: dict, expected: int) -> dict:
        scope = f"pending:{operation}"
        key = str(uuid.uuid4())
        self._keys.set(scope, key)
        last: httpx.Response | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = self._request(
                "POST",
                path,
                json_body=json_body,
                headers={"Idempotency-Key": key},
            )
            if response.status_code == expected:
                return response.json()
            code = _error_envelope(response).get("code", "")
            if _should_retry(response.status_code, code) and attempt < MAX_ATTEMPTS:
                last = response
                if response.status_code == 409:
                    wait = _error_envelope(response).get("retry_after_seconds") or 0
                else:
                    wait = RETRY_BACKOFF_SECONDS * attempt
                self._sleep(float(wait) or RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise OrchestrationError(operation, response.status_code, response.text)
        assert last is not None  # pragma: no cover - loop always sets it on retry
        raise OrchestrationError(operation, last.status_code, last.text)

    def _request(self, method: str, path: str, json_body: dict | None = None, headers: dict | None = None) -> httpx.Response:
        merged = {"x-user-id": self.user_id, **(headers or {})}
        return self._client.request(method, path, json=json_body, headers=merged)
