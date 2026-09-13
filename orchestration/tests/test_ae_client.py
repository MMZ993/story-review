"""Agent Engine (AE) invocation client tests (Phase 8 increment 4, D25).

The AE clients sit behind the same Reviewer/Synthesis/Facilitator client
seams as the HTTP adapter clients and reuse the observability.md transport
policy (short 60 s / 3 jittered; facilitator 120 s / 2 fixed 5 s). The
seams here are injectable: `post` returns (status, parsed) where a 200
body is ``{"events": [...]}`` (the concatenated streamQuery documents),
and the facilitator's session-management reads are injectable callables.
Purely seam-driven (no network, no real model).
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from orchestration.ae_client import (
    AeFacilitatorClient,
    AeReviewerClient,
    final_model_reply,
    parse_stream_documents,
    recovered_turn_reply,
)
from orchestration.agent_clients import (
    AgentTransportError,
    FacilitatorInvocation,
    ReviewerInvocation,
    SynthesisInvocation,
)

from .fakes import review_report, story_detail

RESOURCE = "projects/p/locations/europe-west4/reasoningEngines/123"
SESSION_ID = "sess-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
VERSION = "business-reviewer-abc1234"


def make_settings(**overrides):
    from .conftest import make_settings as base

    values = dict(
        agent_mode="ae",
        ae_business_resource=RESOURCE,
        ae_engineering_resource=RESOURCE,
        ae_synthesis_resource=RESOURCE,
        ae_facilitator_resource=RESOURCE,
        ae_business_version=VERSION,
        ae_engineering_version="engineering-reviewer-abc1234",
        ae_synthesis_version="synthesis-abc1234",
        ae_facilitator_version="facilitator-abc1234",
    )
    values.update(overrides)
    return base(**values)


def review_payload_events() -> list[dict]:
    report = review_report("business", "story-07")
    return [
        {"author": "user", "content": {"parts": [{"text": "## Story under review"}]}},
        {
            "author": "business-reviewer",
            "content": {"parts": [{"text": report.model_dump_json()}]},
        },
    ]


def facilitator_payload_events(turn_output) -> list[dict]:
    return [
        {"author": "user", "content": {"parts": [{"text": "## Turn context"}]}},
        {
            "author": "facilitator",
            "content": {"parts": [{"text": turn_output.model_dump_json()}]},
        },
    ]


def turn_events(turn_number: int, turn_output) -> list[dict]:
    """Session event history as listEvents returns it: one user message per
    turn, each followed by the model's reply."""
    events: list[dict] = []
    for n in range(1, turn_number + 1):
        events += [
            {
                "author": "user",
                "content": {"parts": [{"text": f"... This is turn {n}."}]},
            },
            {
                "author": "facilitator",
                "content": {"parts": [{"text": turn_output.model_dump_json()}]},
            },
        ]
    return events


class PostRecorder:
    """Seam for the AE stream transport: scripted (status, body) replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.sleeps: list[float] = []

    async def post(self, url, json_body, timeout_s: float):
        self.calls.append(
            {"url": url, "json": json_body, "timeout_s": timeout_s}
        )
        if not self.replies:
            raise ConnectionError("down")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def rng(self) -> float:
        return 0.5


# --- stream parsing --------------------------------------------------------


def test_parse_stream_documents_splits_concatenated_json():
    text = '{"author": "user"}\n\n{"author": "agent", "content": {}}'
    events = parse_stream_documents(text)
    assert [e["author"] for e in events] == ["user", "agent"]


def test_final_model_reply_returns_last_non_user_text():
    events = [
        {"author": "user", "content": {"parts": [{"text": "in"}]}},
        {"author": "agent", "content": {"parts": [{"text": "first"}]}},
        {"author": "agent", "content": {"parts": [{"text": "second"}]}},
    ]
    assert final_model_reply(events) == "second"


def test_final_model_reply_empty_when_only_user_text():
    events = [{"author": "user", "content": {"parts": [{"text": "in"}]}}]
    assert final_model_reply(events) == ""


# --- reconciliation matcher (D25 option B) ---------------------------------


def test_recovered_reply_matches_last_own_turn_message():
    from .fakes import opening_turn_output

    events = turn_events(2, opening_turn_output())
    assert recovered_turn_reply(events, 2) is not None


def test_recovered_reply_none_when_last_own_turn_has_no_reply_yet():
    from .fakes import opening_turn_output

    events = turn_events(1, opening_turn_output()) + [
        {"author": "user", "content": {"parts": [{"text": "This is turn 2."}]}},
    ]
    assert recovered_turn_reply(events, 2) is None


def test_recovered_reply_none_for_foreign_turn():
    from .fakes import opening_turn_output

    events = turn_events(3, opening_turn_output())
    assert recovered_turn_reply(events, 2) is None


# --- reviewer client --------------------------------------------------------


async def test_reviewer_invoke_streams_and_validates():
    seam = PostRecorder([(200, {"events": review_payload_events()})])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    result = await client.invoke(ReviewerInvocation(story=story_detail()))
    assert result.report.perspective == "business"
    assert result.agent_version == VERSION
    assert len(seam.calls) == 1
    call = seam.calls[0]
    assert call["url"].endswith(":streamQuery?alt=sse")
    message = call["json"]["input"]["message"]
    assert "## Story under review" in message
    # D25 amendment: AE-mode prompt_sha256 = input fingerprint (the
    # system prompt is baked inside the engine)
    assert result.prompt_sha256 == hashlib.sha256(message.encode()).hexdigest()
    assert call["timeout_s"] == 60.0


async def test_reviewer_retries_transport_failure_then_succeeds():
    seam = PostRecorder(
        [ConnectionError("stream broke"), (200, {"events": review_payload_events()})]
    )
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    result = await client.invoke(ReviewerInvocation(story=story_detail()))
    assert result.report.perspective == "business"
    assert len(seam.calls) == 2


async def test_reviewer_transport_exhaustion_raises():
    seam = PostRecorder([ConnectionError("down"), ConnectionError("down"),
                         ConnectionError("down")])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    with pytest.raises(AgentTransportError):
        await client.invoke(ReviewerInvocation(story=story_detail()))


async def test_reviewer_no_final_text_fails_attempt():
    seam = PostRecorder(
        [(200, {"events": [{"author": "user", "content": {"parts": [{"text": "x"}]}}]}),
         ConnectionError("down"), ConnectionError("down")],
    )
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    with pytest.raises(AgentTransportError):
        await client.invoke(ReviewerInvocation(story=story_detail()))
    assert len(seam.calls) == 3


# --- facilitator client -----------------------------------------------------


def facilitator_invocation(turn_number: int = 1, po_message=None):
    from datetime import UTC, datetime

    from review_schemas import ArtifactReference, SynthesisReport

    run = "run-00000000-0000-4000-8000-000000000001"
    story_id = "story-07"
    reference = ArtifactReference(
        artifact_id="art-00000000-0000-4000-8000-000000000051",
        story_run_id=run,
        type="synthesis",
        perspective=None,
        version=1,
        created_at=datetime.now(UTC),
        content_type="application/json",
        checksum_sha256="a" * 64,
    )
    synthesis = SynthesisReport(
        story_id=story_id,  # type: ignore[arg-type]
        summary="Two findings need PO input.",
        merged_findings=[
            {
                "id": "B-1",
                "title": "Gap found",
                "description": "The story misses an important case.",
                "severity": "minor",
                "category": "completeness",
            }
        ],
        conflicts=[],
        questions_for_po=["Which rate limit applies?"],
        inputs={
            "business": ArtifactReference(
                artifact_id="art-00000000-0000-4000-8000-0000000000b1",
                story_run_id=run,
                type="review-business",
                perspective="business",
                version=1,
                created_at=datetime.now(UTC),
                content_type="application/json",
                checksum_sha256="a" * 64,
            ),
            "engineering": ArtifactReference(
                artifact_id="art-00000000-0000-4000-8000-0000000000e1",
                story_run_id=run,
                type="review-engineering",
                perspective="engineering",
                version=1,
                created_at=datetime.now(UTC),
                content_type="application/json",
                checksum_sha256="a" * 64,
            ),
        },
    )
    return FacilitatorInvocation(
        session_id=SESSION_ID,
        turn_number=turn_number,
        invocation_id=uuid.uuid4(),
        po_message=po_message,
        synthesis_report=synthesis,
        synthesis_reference=reference,
    )


class SessionSeam:
    """Injectable AE session management for the facilitator client."""

    def __init__(self, existing: list[dict] | None = None):
        self.existing = list(existing or [])
        self.created: list[str] = []
        self.events_by_session: dict[str, list[dict]] = {}
        self.event_reads: list[str] = []

    async def list_sessions(self, resource: str, user_id: str) -> list[dict]:
        return [s for s in self.existing if s.get("userId") == user_id]

    async def create_session(self, resource: str, user_id: str) -> dict:
        session = {"id": f"ae-{len(self.created) + 1}", "userId": user_id}
        self.created.append(user_id)
        self.existing.append(session)
        return session

    async def list_events(self, resource: str, user_id: str, session_id: str) -> list[dict]:
        self.event_reads.append(session_id)
        return self.events_by_session.get(session_id, [])


async def test_facilitator_creates_session_and_streams_turn():
    from .fakes import opening_turn_output

    seam = PostRecorder([(200, {"events": facilitator_payload_events(
        opening_turn_output())})])
    sessions = SessionSeam()
    client = AeFacilitatorClient(
        RESOURCE, "facilitator-abc1234", make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
        list_sessions=sessions.list_sessions,
        create_session=sessions.create_session,
        list_events=sessions.list_events,
    )
    request = facilitator_invocation()
    result = await client.invoke(request)
    assert result.output.delegation.invoke == "none"
    assert sessions.created == [request.session_id]
    # the AE session id travels in the stream input
    assert seam.calls[0]["json"]["input"]["session_id"] == "ae-1"
    assert seam.calls[0]["json"]["input"]["user_id"] == request.session_id


async def test_facilitator_reuses_existing_session():
    from .fakes import opening_turn_output

    seam = PostRecorder([(200, {"events": facilitator_payload_events(
        opening_turn_output())})])
    sessions = SessionSeam(existing=[{"id": "ae-9", "userId": SESSION_ID}])
    client = AeFacilitatorClient(
        RESOURCE, "facilitator-abc1234", make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
        list_sessions=sessions.list_sessions,
        create_session=sessions.create_session,
        list_events=sessions.list_events,
    )
    await client.invoke(facilitator_invocation())
    assert sessions.created == []
    assert seam.calls[0]["json"]["input"]["session_id"] == "ae-9"


async def test_facilitator_recovers_from_session_events_between_attempts():
    """D25 option B: after an ambiguous stream failure the client reads the
    AE session events; a recorded reply for this turn is reused and the
    second model attempt never starts."""
    from .fakes import opening_turn_output

    request = facilitator_invocation(turn_number=2, po_message="Please continue.")
    output = opening_turn_output()
    sessions = SessionSeam(existing=[{"id": "ae-1", "userId": request.session_id}])
    sessions.events_by_session["ae-1"] = turn_events(2, output)
    seam = PostRecorder([ConnectionError("stream died mid-turn")])
    client = AeFacilitatorClient(
        RESOURCE, "facilitator-abc1234", make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
        list_sessions=sessions.list_sessions,
        create_session=sessions.create_session,
        list_events=sessions.list_events,
    )
    result = await client.invoke(request)
    assert result.output == output
    assert len(seam.calls) == 1  # no second model attempt
    assert sessions.event_reads == ["ae-1"]


async def test_facilitator_recovers_none_when_turn_not_in_events():
    from .fakes import opening_turn_output

    request = facilitator_invocation(turn_number=2, po_message="Please continue.")
    sessions = SessionSeam(existing=[{"id": "ae-1", "userId": request.session_id}])
    sessions.events_by_session["ae-1"] = turn_events(1, opening_turn_output())
    seam = PostRecorder(
        [ConnectionError("stream died"), (200, {"events": facilitator_payload_events(
            opening_turn_output())})]
    )
    client = AeFacilitatorClient(
        RESOURCE, "facilitator-abc1234", make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
        list_sessions=sessions.list_sessions,
        create_session=sessions.create_session,
        list_events=sessions.list_events,
    )
    result = await client.invoke(request)
    assert len(seam.calls) == 2
    assert seam.sleeps == [5.0]


# --- configuration (agent mode selection, D25) ------------------------------


def _base_env() -> dict[str, str]:
    return {
        "ORCH_DB_DSN": "postgresql://x",
        "ORCH_STORY_URL": "http://story:8080/mcp",
        "ORCH_ARTIFACT_URL": "http://artifact:8080/mcp",
        "ORCH_REPORT_URL": "http://report:8080/mcp",
        "ORCH_BUCKET": "artifacts-local",
        "ORCH_BUSINESS_URL": "http://business:8080",
        "ORCH_ENGINEERING_URL": "http://engineering:8080",
        "ORCH_SYNTHESIS_URL": "http://synthesis:8080",
        "ORCH_FACILITATOR_URL": "http://facilitator:8080",
    }


def _ae_env() -> dict[str, str]:
    env = _base_env()
    env.update(
        {
            "ORCH_AGENT_MODE": "ae",
            "ORCH_AE_BUSINESS_RESOURCE": RESOURCE,
            "ORCH_AE_ENGINEERING_RESOURCE": RESOURCE,
            "ORCH_AE_SYNTHESIS_RESOURCE": RESOURCE,
            "ORCH_AE_FACILITATOR_RESOURCE": RESOURCE,
            "ORCH_AE_BUSINESS_VERSION": "business-reviewer-x",
            "ORCH_AE_ENGINEERING_VERSION": "engineering-reviewer-x",
            "ORCH_AE_SYNTHESIS_VERSION": "synthesis-x",
            "ORCH_AE_FACILITATOR_VERSION": "facilitator-x",
        }
    )
    return env


def test_config_defaults_to_http_mode():
    from orchestration.config import Settings

    settings = Settings.from_env(_base_env())
    assert settings.agent_mode == "http"
    assert settings.ae_business_resource is None


def test_config_ae_mode_requires_pointer_variables():
    from orchestration.config import Settings

    env = _ae_env()
    del env["ORCH_AE_FACILITATOR_RESOURCE"]
    with pytest.raises(ValueError, match="ORCH_AE_FACILITATOR_RESOURCE"):
        Settings.from_env(env)


def test_config_ae_mode_rejects_missing_adapter_urls():
    """In ae mode the adapter URLs are optional — the engine pointers
    replace them."""
    from orchestration.config import Settings

    env = _ae_env()
    for name in (
        "ORCH_BUSINESS_URL", "ORCH_ENGINEERING_URL",
        "ORCH_SYNTHESIS_URL", "ORCH_FACILITATOR_URL",
    ):
        del env[name]
    settings = Settings.from_env(env)
    assert settings.agent_mode == "ae"
    assert settings.ae_facilitator_version == "facilitator-x"


def test_config_rejects_unknown_mode():
    from orchestration.config import Settings

    env = _base_env() | {"ORCH_AGENT_MODE": "carrier-pigeon"}
    with pytest.raises(ValueError, match="ORCH_AGENT_MODE"):
        Settings.from_env(env)


def test_default_agent_set_branches_on_mode():
    from orchestration.agent_clients import (
        HttpFacilitatorClient, HttpReviewerClient, default_agent_set,
    )
    from orchestration.ae_client import AeFacilitatorClient, AeReviewerClient
    from orchestration.config import Settings

    http = default_agent_set(Settings.from_env(_base_env()))
    assert isinstance(http.business, HttpReviewerClient)
    ae = default_agent_set(Settings.from_env(_ae_env()))
    assert isinstance(ae.business, AeReviewerClient)
    assert isinstance(ae.facilitator, AeFacilitatorClient)


# --- review fixes: transport wiring, retryable envelopes, matcher edges ----


def test_ae_agent_set_wires_the_stream_transport_into_all_four_clients():
    from orchestration.ae_client import _ae_stream_post, ae_agent_set

    agents = ae_agent_set(make_settings())
    for client in (
        agents.business, agents.engineering, agents.synthesis, agents.facilitator,
    ):
        assert client._post is _ae_stream_post


async def test_reviewer_retries_retryable_error_envelope():
    """A retryable AE 503 envelope is retried, matching the shared
    transport policy (not a terminal failure)."""
    error = {
        "error": {
            "code": "UPSTREAM_UNAVAILABLE",
            "message": "backend error",
            "agent": "agent-engine",
            "correlation_id": "77777777-7777-4777-8777-777777777777",
            "retryable": True,
            "retry_after_seconds": 5,
        }
    }
    seam = PostRecorder([(503, error), (200, {"events": review_payload_events()})])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    result = await client.invoke(ReviewerInvocation(story=story_detail()))
    assert result.report.perspective == "business"
    assert len(seam.calls) == 2


async def test_reviewer_non_retryable_envelope_is_terminal():
    from orchestration.agent_clients import AgentCallFailure

    error = {
        "error": {
            "code": "FORBIDDEN",
            "message": "invoker lacks permission",
            "agent": "agent-engine",
            "correlation_id": "77777777-7777-4777-8777-777777777777",
            "retryable": False,
        }
    }
    seam = PostRecorder([(403, error)])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    with pytest.raises(AgentCallFailure) as excinfo:
        await client.invoke(ReviewerInvocation(story=story_detail()))
    assert excinfo.value.error.code == "FORBIDDEN"
    assert len(seam.calls) == 1


async def test_reviewer_invalid_final_reply_is_terminal_validation_error():
    from orchestration.agent_clients import AgentCallFailure

    events = [
        {"author": "agent", "content": {"parts": [{"text": "not json at all"}]}},
    ]
    seam = PostRecorder([(200, {"events": events})])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    with pytest.raises(AgentCallFailure) as excinfo:
        await client.invoke(ReviewerInvocation(story=story_detail()))
    assert excinfo.value.error.code == "VALIDATION_ERROR"
    assert not excinfo.value.error.retryable


def test_parse_stream_documents_tolerates_sse_data_prefix():
    text = 'data: {"author": "user"}\n\ndata: {"author": "agent"}'
    assert len(parse_stream_documents(text)) == 2


def test_recovered_reply_turn_1_does_not_match_turn_10():
    from .fakes import opening_turn_output

    events = turn_events(10, opening_turn_output())
    assert recovered_turn_reply(events, 1) is None
    assert recovered_turn_reply(events, 10) is not None


def test_recovered_reply_none_when_later_foreign_user_message():
    """A later user message without our marker means the reply after our
    message cannot be attributed — no recovery."""
    from .fakes import opening_turn_output

    events = turn_events(1, opening_turn_output())
    events += [
        {"author": "user", "content": {"parts": [{"text": "lease took over"}]}},
    ]
    assert recovered_turn_reply(events, 1) is None


def test_endpoint_rejects_malformed_resource():
    from orchestration.ae_client import _endpoint

    with pytest.raises(ValueError, match="malformed"):
        _endpoint("projects/p/reasoningEngines/1")


# --- re-review fixes: exhausted envelopes, recovery on envelope path --------


async def test_facilitator_reconciles_on_retryable_envelope_between_attempts():
    """A retryable error envelope (not just a transport exception) is an
    ambiguous outcome: the AE session store is consulted before retry."""
    request = facilitator_invocation()
    error = {
        "error": {
            "code": "UPSTREAM_UNAVAILABLE", "message": "backend error",
            "agent": "agent-engine",
            "correlation_id": "77777777-7777-4777-8777-777777777777",
            "retryable": True, "retry_after_seconds": 5,
        }
    }
    seam = PostRecorder([(503, error), (200, {"events": facilitator_payload_events(
        __import__("tests.fakes", fromlist=["opening_turn_output"]).opening_turn_output())})])
    sessions = SessionSeam(existing=[{"id": "ae-1", "userId": request.session_id}])
    client = AeFacilitatorClient(
        RESOURCE, "facilitator-abc1234", make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
        list_sessions=sessions.list_sessions,
        create_session=sessions.create_session,
        list_events=sessions.list_events,
    )
    await client.invoke(request)
    assert sessions.event_reads == ["ae-1"]  # recovery ran between attempts
    assert len(seam.calls) == 2


async def test_exhausted_retryable_envelope_keeps_structured_form():
    from orchestration.agent_clients import AgentCallFailure

    error = {
        "error": {
            "code": "UPSTREAM_UNAVAILABLE", "message": "backend error",
            "agent": "agent-engine",
            "correlation_id": "77777777-7777-4777-8777-777777777777",
            "retryable": True, "retry_after_seconds": 5,
        }
    }
    seam = PostRecorder([(503, error), (503, error), (503, error)])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    with pytest.raises(AgentCallFailure) as excinfo:
        await client.invoke(ReviewerInvocation(story=story_detail()))
    assert excinfo.value.error.code == "UPSTREAM_UNAVAILABLE"


async def test_reviewer_user_id_is_per_invocation():
    seam = PostRecorder([
        (200, {"events": review_payload_events()}),
        (200, {"events": review_payload_events()}),
    ])
    client = AeReviewerClient(
        RESOURCE, VERSION, make_settings(), post=seam.post,
        sleeper=seam.sleep, rng=seam.rng,
    )
    await client.invoke(ReviewerInvocation(story=story_detail()))
    await client.invoke(ReviewerInvocation(story=story_detail()))
    first = seam.calls[0]["json"]["input"]["user_id"]
    second = seam.calls[1]["json"]["input"]["user_id"]
    assert first.startswith("orch-") and second.startswith("orch-")
    assert first != second


async def test_facilitator_deadline_exceeded_propagates():
    import time as _time

    from orchestration.agent_clients import DeadlineExceeded

    request = facilitator_invocation()
    sessions = SessionSeam(existing=[{"id": "ae-1", "userId": request.session_id}])
    client = AeFacilitatorClient(
        RESOURCE, "facilitator-abc1234", make_settings(),
        post=(lambda *a: None),  # never reached
        list_sessions=sessions.list_sessions,
        create_session=sessions.create_session,
        list_events=sessions.list_events,
    )
    with pytest.raises(DeadlineExceeded):
        await client.invoke(request, deadline=_time.monotonic() - 1)


class TestRuntimeQueryEnvelope:
    async def test_unwraps_output_envelope(self, monkeypatch):
        """Live-verified at the inc-4 gate: :query wraps the method return
        under `output`."""
        from orchestration import ae_client as mod

        class FakeResponse:
            status_code = 200
            text = "{}"
            def json(self):
                return {"output": {"sessions": []}}

        class FakeClient:
            def __init__(self, timeout=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None, headers=None):
                return FakeResponse()

        monkeypatch.setattr(mod.httpx, "AsyncClient", FakeClient)
        monkeypatch.setattr(
            mod, "_bearer_token", lambda: "tok", raising=False
        )
        body = await mod._runtime_query(
            "projects/p/locations/l/reasoningEngines/e1", "list_sessions", {}
        )
        assert body == {"sessions": []}


class TestRuntimeSessionRoutes:
    """Live-verified at the inc-4 gate: session state lives behind the
    agent-runtime :query methods (create_session / list_sessions /
    get_session), NOT the control-plane /sessions REST routes (whose
    numeric sessions the runtime cannot see — SessionNotFoundError)."""

    async def test_list_uses_runtime_query_server_filtered(self, monkeypatch):
        from orchestration import ae_client as mod

        seen = {}

        async def fake_query(resource, class_method, inputs, timeout_s=10.0):
            seen.update(resource=resource, class_method=class_method, inputs=inputs)
            return {"sessions": [{"id": "s1", "userId": "want"}]}

        monkeypatch.setattr(mod, "_runtime_query", fake_query)
        sessions = await mod._real_list_sessions(
            "projects/p/locations/l/reasoningEngines/e1", "want"
        )
        assert seen["class_method"] == "list_sessions"
        assert seen["inputs"] == {"user_id": "want"}
        assert sessions == [{"id": "s1", "userId": "want"}]

    async def test_create_uses_runtime_create_session(self, monkeypatch):
        from orchestration import ae_client as mod

        seen = {}

        async def fake_query(resource, class_method, inputs, timeout_s=10.0):
            seen.update(class_method=class_method, inputs=inputs)
            return {"id": "uuid-1", "userId": "want"}

        monkeypatch.setattr(mod, "_runtime_query", fake_query)
        session = await mod._real_create_session("engines/e1", "want")
        assert seen["class_method"] == "create_session"
        assert seen["inputs"] == {"user_id": "want"}
        assert session["id"] == "uuid-1"

    async def test_events_via_get_session_with_recent_events(self, monkeypatch):
        from orchestration import ae_client as mod

        seen = {}

        async def fake_query(resource, class_method, inputs, timeout_s=10.0):
            seen.update(class_method=class_method, inputs=inputs)
            return {"id": "s1", "events": [{"author": "user", "content": {}}]}

        monkeypatch.setattr(mod, "_runtime_query", fake_query)
        events = await mod._real_list_events("engines/e1", "want", "s1")
        assert seen["class_method"] == "get_session"
        assert seen["inputs"]["session_id"] == "s1"
        assert len(events) == 1


