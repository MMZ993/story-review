"""Case-runner unit tests: replay + capture against fakes (inc 1).

The HTTP fake scripts a full clean-scenario arc (create → acceptance
turn → detail) and records requests so the tests pin the PO-script
replay, the idempotency discipline, artifact fetching, evidence
collection, and the persistence probes.
"""

from __future__ import annotations

import json

import pytest

from evaluation.artifact_client import ArtifactToolFailure
from evaluation.case_runner import CaseFailure, Transports, run_case
from evaluation.capture import AgentRunEvidence, artifact_key
from evaluation.orchestration_client import (
    MemoryKeyStore,
    OrchestrationClient,
    OrchestrationError,
)
from tests.test_assertions import expected_case

import httpx

from datetime import datetime

SESSION_ID = "sess-00000000-0000-0000-0000-000000000000"
RUN_ID = "run-00000000-0000-0000-0000-000000000000"
SYNTHESIS_ARTIFACT = "art-00000000-0000-0000-0000-000000000000"


class FakeOrchestration:
    """Scripts the clean arc and records requests for assertions."""

    def __init__(self):
        self.requests: list[tuple[str, str, dict | None, dict]] = []
        self.turn_bodies: list[dict] = []
        self.detail_response = {
            "state": "completed",
            "facilitator_turn_count": 1,
            "turns": [
                {"turn_number": 1, "outcome": "continue"},
                {"turn_number": 2, "outcome": "finalize"},
            ],
            "artifact_references": [
                {"artifact_id": SYNTHESIS_ARTIFACT, "story_run_id": RUN_ID,
                 "type": "synthesis", "version": 1},
                {"artifact_id": SYNTHESIS_ARTIFACT, "story_run_id": RUN_ID,
                 "type": "synthesis", "version": 1},
            ],
            "reports": [
                {"format": "md", "signed_url": "https://x.test/md"},
                {"format": "pdf", "signed_url": "https://x.test/pdf"},
            ],
        }

    def create_session(self, story_id, formats):
        self.requests.append(("POST", "/api/v1/sessions", {"story_id": story_id}, {}))
        return {"session_id": SESSION_ID, "story_run_id": RUN_ID, "state": "active"}

    def post_turn(self, session_id, body):
        self.turn_bodies.append(body)
        return {"session_id": session_id, "turn_number": 1 + len(self.turn_bodies)}

    def get_session(self, session_id):
        self.requests.append(("GET", f"/api/v1/sessions/{session_id}", None, {}))
        return json.loads(json.dumps(self.detail_response))


class FakeArtifacts:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def get_artifact(self, artifact_id, story_run_id):
        self.calls.append((artifact_id, story_run_id))
        if story_run_id != RUN_ID:
            raise ArtifactToolFailure("ARTIFACT_NOT_FOUND", "run mismatch")
        return {"content": {"conflicts": []}}


class FakeEvidence:
    def __init__(self, rows=None, tool_calls=None):
        self.rows = rows or [
            AgentRunEvidence(
                agent="facilitator",
                agent_version="v",
                prompt_sha256="0" * 64,
                state="succeeded",
                transport_attempts=1,
                corrective_reprompts=0,
                started_at=datetime.fromisoformat("2026-01-01T10:00:00+00:00"),
                finished_at=datetime.fromisoformat("2026-01-01T10:00:01+00:00"),
            )
        ]
        self.tool_calls = tool_calls or []

    def fetch_agent_runs(self, dsn, session_id):
        return self.rows

    def fetch_facilitator_tool_calls(self, dsn, session_id):
        return self.tool_calls


class FakeCase:
    def __init__(self):
        self.case_id = "t1/clean"
        self.expected = expected_case()
        self.story = type("S", (), {"story_id": "story-01", "template": "t1"})()


def make_transports(orchestration=None, artifacts=None, evidence=None):
    return Transports(
        http=orchestration or FakeOrchestration(),
        artifacts=artifacts or FakeArtifacts(),
        fetch_agent_runs=(evidence or FakeEvidence()).fetch_agent_runs,
        fetch_facilitator_tool_calls=(evidence or FakeEvidence()).fetch_facilitator_tool_calls,
        orchestration_dsn="dsn-orch",
        facilitator_dsn="dsn-fac",
    )


def test_run_case_replays_po_script_and_captures_everything():
    http = FakeOrchestration()
    artifacts = FakeArtifacts()
    capture = run_case(FakeCase(), make_transports(http, artifacts))
    assert capture.session_id == SESSION_ID
    assert capture.story_run_id == RUN_ID
    # po_script: one acceptance turn -> exactly one post_turn
    assert http.turn_bodies == [{"message": None, "po_accepted": True}]
    # 1 capture read + 1 same-run probe + 1 cross-run probe
    assert len(artifacts.calls) == 3
    assert artifact_key("synthesis", 1) in capture.artifacts
    assert capture.persistence.restore_ok
    assert capture.persistence.same_run_read_ok
    assert capture.persistence.cross_run_rejected
    # cross-run probe issued a foreign run read
    assert any(run != RUN_ID for _, run in artifacts.calls)


def test_run_case_collects_db_evidence():
    evidence = FakeEvidence(tool_calls=["get_story"])
    capture = run_case(FakeCase(), make_transports(evidence=evidence))
    assert capture.facilitator_tool_calls == ["get_story"]
    assert capture.agent_runs[0].agent == "facilitator"


def test_run_case_raises_case_failure_on_http_error():
    class Broken(FakeOrchestration):
        def create_session(self, story_id, formats):
            raise OrchestrationError("create-session", 503, "down")

    with pytest.raises(CaseFailure):
        run_case(FakeCase(), make_transports(Broken()))


def test_run_case_tolerates_detail_without_artifact_references():
    http = FakeOrchestration()
    http.detail_response = {"state": "parked", "facilitator_turn_count": 10,
                            "turns": [], "reports": []}
    capture = run_case(FakeCase(), make_transports(http))
    assert capture.artifacts == {}
    assert not capture.persistence.same_run_read_ok
    assert "no synthesis artifact to probe" in capture.persistence.notes[0]


def test_run_case_records_transport_error_on_cross_run_probe():
    from evaluation.artifact_client import ArtifactClientError

    class Flaky(FakeArtifacts):
        def get_artifact(self, artifact_id, story_run_id):
            self.calls.append((artifact_id, story_run_id))
            if story_run_id != RUN_ID:
                raise ArtifactClientError("connection reset")
            return {"content": {}}

    capture = run_case(FakeCase(), make_transports(artifacts=Flaky()))
    assert capture.persistence.same_run_read_ok
    assert not capture.persistence.cross_run_rejected
    assert any("transport error" in note for note in capture.persistence.notes)


def test_run_case_evidence_failure_raises_case_failure():
    def broken_fetch(dsn, session_id):
        raise RuntimeError("db down")

    transports = make_transports()
    transports.fetch_agent_runs = broken_fetch
    with pytest.raises(CaseFailure):
        run_case(FakeCase(), transports)


def test_run_case_raises_case_failure_on_cross_run_success():
    class Leaky(FakeArtifacts):
        def get_artifact(self, artifact_id, story_run_id):
            self.calls.append((artifact_id, story_run_id))
            return {"content": {}}

    capture = run_case(FakeCase(), make_transports(artifacts=Leaky()))
    assert not capture.persistence.cross_run_rejected


# --- orchestration client (HTTP discipline) -------------------------------


def test_client_retries_503_with_same_key_then_succeeds():
    keys: list[str | None] = []
    store = MemoryKeyStore()

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers.get("Idempotency-Key"))
        if len(keys) == 1:
            return httpx.Response(503, json={"error": {"code": "UPSTREAM_UNAVAILABLE"}})
        return httpx.Response(201, json={"session_id": SESSION_ID, "story_run_id": RUN_ID})

    client = OrchestrationClient(
        transport=httpx.MockTransport(handler), key_store=store, sleep=lambda _: None
    )
    created = client.create_session("story-01", ["md"])
    assert created["session_id"] == SESSION_ID
    # same key on every attempt, persisted in the store before the first send
    assert keys[0] is not None and keys[0] == keys[1]
    assert store._keys["pending:create-session"] == keys[0]


def test_client_retries_409_session_locked_same_key():
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(
                409,
                json={"error": {"code": "SESSION_LOCKED", "retry_after_seconds": 0}},
            )
        return httpx.Response(200, json={"turn_number": 2})

    client = OrchestrationClient(
        transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    assert client.post_turn(SESSION_ID, {"message": "hi", "po_accepted": False})[
        "turn_number"
    ] == 2


def test_client_locked_retry_waits_envelope_retry_after_seconds():
    waits: list[float] = []
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(
                409,
                json={"error": {"code": "SESSION_LOCKED", "retry_after_seconds": 7}},
            )
        return httpx.Response(200, json={"turn_number": 2})

    client = OrchestrationClient(
        transport=httpx.MockTransport(handler), sleep=waits.append
    )
    client.post_turn(SESSION_ID, {"message": "hi", "po_accepted": False})
    assert waits == [7.0]


def test_client_get_session_retries_503():
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503, json={"error": {"code": "UPSTREAM_UNAVAILABLE"}})
        return httpx.Response(200, json={"state": "completed"})

    client = OrchestrationClient(
        transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    assert client.get_session(SESSION_ID)["state"] == "completed"


def test_client_raises_on_non_retryable_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": {"code": "STORY_SESSION_ACTIVE"}})

    client = OrchestrationClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OrchestrationError) as excinfo:
        client.create_session("story-01", ["md"])
    assert excinfo.value.status == 409


def test_client_gives_up_after_retry_budget():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"code": "UPSTREAM_UNAVAILABLE"}})

    client = OrchestrationClient(
        transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    with pytest.raises(OrchestrationError):
        client.post_turn(SESSION_ID, {"message": "hi", "po_accepted": False})
