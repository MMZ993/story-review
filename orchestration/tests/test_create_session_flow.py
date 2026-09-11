"""Flow 1 (session creation) deterministic tests — fake agent clients and
scripted MCP seams, real Postgres via the throwaway-pool fixture.

Covers: happy path (201 + durable records + artifact saves), key replay
(no duplicate side effects), partial-failure recovery via replay, takeover
of a crashed in-progress claim, active-session 409, idempotency-key reuse
409, unknown story 404.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid

import httpx
import pytest

from orchestration.config import Settings
from orchestration.main import create_app
from orchestration.mcp_client import McpClient

from .fakes import (
    FakeArtifactMcp,
    opening_turn_output,
    review_report,
    story_detail,
    story_transport,
)

KEY_A = "22222222-2222-4222-8222-222222222222"
KEY_B = "33333333-3333-4333-8333-333333333333"
CORR = "44444444-4444-4444-8444-444444444444"


async def _no_sleep(seconds: float) -> None:
    pass


class FakeReviewer:
    """In-process frozen-contract reviewer client (typed output or failure)."""

    def __init__(self, perspective: str):
        self.perspective = perspective
        self.calls: list = []
        self.transport_failures_left = 0

    async def invoke(self, request, *, deadline: float):
        from orchestration.agent_clients import ReviewerResult

        self.calls.append(request)
        if self.transport_failures_left > 0:
            self.transport_failures_left -= 1
            raise asyncio.TimeoutError("model call timed out")
        return ReviewerResult(
            report=review_report(self.perspective, request.story.story_id),
            agent_version="0.1.0",
            prompt_sha256="c" * 64,
        )


class FakeSynthesis:
    def __init__(self):
        self.calls: list = []

    async def invoke(self, request, *, deadline: float):
        from review_schemas.synthesis import SynthesisReport

        from orchestration.agent_clients import SynthesisResult

        self.calls.append(request)
        report = SynthesisReport(
            story_id=request.business.report.story_id,
            summary="Merged review of both perspectives.",
            merged_findings=[
                {
                    "id": "B-1",
                    "title": "Gap found",
                    "description": "The story misses an important case.",
                    "severity": "minor",
                    "category": "completeness",
                },
                {
                    "id": "E-1",
                    "title": "Gap found",
                    "description": "The story misses an important case.",
                    "severity": "minor",
                    "category": "completeness",
                },
            ],
            conflicts=[],
            questions_for_po=["Which rate limit applies?"],
            inputs={
                "business": request.business.reference,
                "engineering": request.engineering.reference,
            },
        )
        return SynthesisResult(
            report=report, agent_version="0.1.0", prompt_sha256="d" * 64
        )


class FakeFacilitator:
    def __init__(self):
        self.calls: list = []

    async def invoke(self, request, *, deadline: float):
        from orchestration.agent_clients import FacilitatorResult

        self.calls.append(request)
        return FacilitatorResult(
            output=opening_turn_output(),
            agent_version="0.1.0",
            prompt_sha256="e" * 64,
            corrective_reprompts=0,
        )


def make_agents():
    from orchestration.agent_clients import AgentSet

    return AgentSet(
        business=FakeReviewer("business"),
        engineering=FakeReviewer("engineering"),
        synthesis=FakeSynthesis(),
        facilitator=FakeFacilitator(),
    )


def flow_client(
    settings: Settings,
    pool,
    artifact: FakeArtifactMcp,
    agents,
    detail=None,
    report=None,
) -> httpx.AsyncClient:
    detail = detail or story_detail()
    from .fakes import FakeReportMcp

    report = report if report is not None else FakeReportMcp(artifact)

    def client(url, transport):
        return McpClient(
            url=url, settings=settings, session_call=transport, sleeper=_no_sleep
        )

    app = create_app(
        settings=settings,
        pool=pool,
        story_client=client(settings.story_url, story_transport(detail)),
        artifact_client=client(settings.artifact_url, artifact),
        report_client=client(settings.report_url, report),
        agents=agents,
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://orch"
    )


def create_payload(story_id: str = "story-07", formats=("md",)) -> dict:
    return {"story_id": story_id, "requested_formats": list(formats)}


async def post_create(
    client: httpx.AsyncClient, key: str, payload: dict
) -> httpx.Response:
    return await client.post(
        "/api/v1/sessions",
        json=payload,
        headers={"Idempotency-Key": key, "X-Correlation-Id": CORR},
    )


@pytest.fixture
def artifact():
    return FakeArtifactMcp()


@pytest.fixture
def agents():
    return make_agents()


@pytest.fixture
def settings():
    from .conftest import make_settings

    return make_settings()


@pytest.fixture
def client(pool, settings, artifact, agents):
    # ASGI client owned per-test (owns the app lifespan)
    return flow_client(settings, pool, artifact, agents)


async def assert_flow_state(pool, body: dict, artifact: FakeArtifactMcp):
    """Shared durable-state assertions after a successful creation."""
    session_id, run_id = body["session_id"], body["story_run_id"]
    async with pool.acquire() as conn:
        session = await conn.fetchrow(
            "select * from sessions where session_id = $1", session_id
        )
        assert session is not None and session["state"] == "active"
        assert session["facilitator_turn_count"] == 1
        assert session["requested_formats"] == ["md"]
        turn = await conn.fetchrow(
            "select * from turns where session_id = $1 and turn_number = 1", session_id
        )
        assert turn is not None and turn["state"] == "succeeded"
        assert turn["po_message"] is None and turn["outcome"] == "continue"
        import json as _json
        delegation = _json.loads(turn["delegation"])
        assert delegation["invoke"] == "none"
        assert turn["facilitator_reply"] == body["facilitator_reply"]
        agent_runs = await conn.fetch(
            "select agent from agent_runs where story_run_id = $1", run_id
        )
        assert sorted(row["agent"] for row in agent_runs) == [
            "business-reviewer",
            "engineering-reviewer",
            "facilitator",
            "synthesis",
        ]
        claims = await conn.fetchrow(
            "select state from idempotency_claims where idempotency_key = $1",
            uuid.UUID(KEY_A),
        )
        assert claims["state"] == "completed"
    assert len(artifact._by_slot) == 4
    # response invariants mirrored by the strict model already:
    assert body["delegation"]["invoke"] == "none"
    assert body["synthesis"]["story_run_id"] == run_id
    assert len(body["artifact_references"]) == 4


async def test_create_session_success(client, pool, artifact):
    response = await post_create(client, KEY_A, create_payload())
    assert response.status_code == 201, response.text
    body = response.json()
    await assert_flow_state(pool, body, artifact)


async def test_create_session_replay_is_side_effect_free(client, pool, artifact, agents):
    first = await post_create(client, KEY_A, create_payload())
    assert first.status_code == 201
    saves_before = len(artifact.save_calls)
    calls_before = (
        len(agents.business.calls),
        len(agents.engineering.calls),
        len(agents.synthesis.calls),
        len(agents.facilitator.calls),
    )
    second = await post_create(client, KEY_A, create_payload())
    assert second.status_code == 201
    assert second.json() == first.json()
    assert len(artifact.save_calls) == saves_before
    assert (
        len(agents.business.calls),
        len(agents.engineering.calls),
        len(agents.synthesis.calls),
        len(agents.facilitator.calls),
    ) == calls_before


async def test_partial_failure_recovers_via_key_replay(
    pool, settings, artifact, agents
):
    agents.business.transport_failures_left = 5  # retry policy exhausts -> 503
    client = flow_client(settings, pool, artifact, agents)
    failed = await post_create(client, KEY_A, create_payload())
    assert failed.status_code == 503, failed.text
    assert failed.json()["error"]["retryable"] is True

    agents.business.transport_failures_left = 0  # recovered
    recovered = await post_create(client, KEY_A, create_payload())
    assert recovered.status_code == 201, recovered.text
    body = recovered.json()
    await assert_flow_state(pool, body, artifact)
    # no duplicate artifacts despite the failed first attempt's saves
    assert len(artifact._by_slot) == 4


async def test_crashed_in_progress_claim_is_taken_over(client, pool):
    async with pool.acquire() as conn:
        await conn.execute(
            "insert into idempotency_claims (route, session_id, idempotency_key, "
            "request_fingerprint, state, created_at, updated_at) values "
            "($1, '', $2, $3, 'in_progress', now(), now())",
            "POST /api/v1/sessions",
            uuid.UUID(KEY_A),
            hashlib.sha256(
                json.dumps(create_payload(), sort_keys=True).encode()
            ).hexdigest(),
        )
    response = await post_create(client, KEY_A, create_payload())
    assert response.status_code == 201, response.text


async def test_active_session_conflict_409(client, agents):
    first = await post_create(client, KEY_A, create_payload())
    assert first.status_code == 201
    second = await post_create(client, KEY_B, create_payload())
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "STORY_SESSION_ACTIVE"
    assert second.json()["error"]["retryable"] is False


async def test_idempotency_key_reused_409(client):
    first = await post_create(client, KEY_A, create_payload())
    assert first.status_code == 201
    reused = await post_create(
        client, KEY_A, create_payload(formats=("pdf",))
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_unknown_story_404(client):
    response = await post_create(client, KEY_A, create_payload("story-99"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STORY_NOT_FOUND"


async def test_missing_idempotency_key_422(client):
    response = await client.post("/api/v1/sessions", json=create_payload())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_synthesis_receives_both_perspectives(client, agents):
    response = await post_create(client, KEY_A, create_payload())
    assert response.status_code == 201
    request = agents.synthesis.calls[0]
    assert request.business.report.perspective == "business"
    assert request.engineering.report.perspective == "engineering"
    assert (
        request.business.reference.story_run_id
        == request.engineering.reference.story_run_id
    )
    facilitator_request = agents.facilitator.calls[0]
    assert facilitator_request.turn_number == 1
    assert facilitator_request.po_message is None
    assert facilitator_request.synthesis_reference.type == "synthesis"
    assert len(facilitator_request.evidence_references) == 3


async def test_delegating_opening_turn_is_structured_422(pool, settings, artifact, agents):
    from review_schemas.facilitator import DelegationDecision

    from .fakes import opening_turn_output

    bad = opening_turn_output()
    bad.delegation = DelegationDecision(
        invoke="both", open_issues=["x"], readiness="needs_work"
    )

    async def invoke(request, *, deadline):
        from orchestration.agent_clients import FacilitatorResult

        return FacilitatorResult(
            output=bad, agent_version="0.1.0", prompt_sha256="e" * 64
        )

    agents.facilitator.invoke = invoke
    client = flow_client(settings, pool, artifact, agents)
    response = await post_create(client, KEY_A, create_payload())
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] == "DELEGATION_VALIDATION"
    assert body["error"]["retryable"] is False


async def test_non_v4_idempotency_key_422(client):
    response = await client.post(
        "/api/v1/sessions",
        json=create_payload(),
        headers={"Idempotency-Key": "55555555-5555-5555-8555-555555555555"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
