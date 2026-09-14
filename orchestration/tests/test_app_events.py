"""FastAPI application events (observability.md "Callbacks and application
events" / "Loop safety and dashboards", increment-6 slice C): the alertable
failure conditions (retry exhaustion, delegation-validation failure) and the
gate/park decisions emit structured events on the ``storyreview.app``
logger, which the JSON handler carries to Cloud Logging and slice C's
log-based Cloud Monitoring metrics filter on (``event`` field).

Behavior-oriented: each test drives a real route through the app factory
(fakes + throwaway Postgres) and asserts on the captured log records —
same harness as the flow tests, no LiveLog plumbing.
"""

from __future__ import annotations

import logging
import uuid

import pytest

from review_schemas.errors import ErrorBody

from orchestration.agent_clients import AgentCallFailure, AgentTransportError

from .fakes import FakeArtifactMcp
from .test_turns_flow import (
    ScriptedFacilitator,
    create_session_with,
    dialogue_client,
    dialogue_output,
    post_turn,
)


class CaptureHandler(logging.Handler):
    """Collect records so assertions can run against attributes (the
    `storyreview` logger does not propagate, so caplog cannot see it)."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def app_events():
    handler = CaptureHandler()
    logger = logging.getLogger("storyreview.app")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


def find_event(app_events, name: str) -> logging.LogRecord:
    """The (single) captured record whose ``event`` field is ``name``."""
    matches = [r for r in app_events.records if r.event == name]
    assert len(matches) == 1, f"expected exactly one {name!r} event"
    return matches[0]


# --- local fixtures (mirror test_turns_flow) -------------------------------


@pytest.fixture
def settings():
    from .conftest import make_settings

    return make_settings()


@pytest.fixture
def artifact():
    return FakeArtifactMcp()


# --- gate / park events ----------------------------------------------------


async def test_parked_turn_emits_gate_decision_and_park_events(
    pool, settings, artifact, app_events
):
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)
    async with pool.acquire() as conn:
        await conn.execute(
            "update sessions set facilitator_turn_count = 9 "
            "where session_id = $1",
            session["session_id"],
        )

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "park"

    gate = find_event(app_events, "gate_decision")
    assert gate.outcome == "park"
    assert gate.facilitator_turn == 10
    assert gate.session_id == session["session_id"]

    parked = find_event(app_events, "session_parked")
    assert parked.session_id == session["session_id"]
    assert parked.facilitator_turn == 10


async def test_continuing_turn_emits_gate_decision_only(
    pool, settings, artifact, app_events
):
    facilitator = ScriptedFacilitator([dialogue_output("none")])
    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, facilitator)

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "continue"

    gate = find_event(app_events, "gate_decision")
    assert gate.outcome == "continue"
    assert gate.facilitator_turn == 2
    assert [r for r in app_events.records if r.event == "session_parked"] == []


# --- alertable failure events -----------------------------------------------


async def test_delegation_validation_failure_emits_alert_event(
    pool, settings, artifact, app_events
):
    class InvalidFacilitator(ScriptedFacilitator):
        async def invoke(self, request, *, deadline):
            raise AgentCallFailure(
                ErrorBody(
                    code="DELEGATION_VALIDATION",
                    message="exhausted corrective re-prompts",
                    correlation_id=uuid.uuid4(),
                    retryable=False,
                )
            )

    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, InvalidFacilitator([]))

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DELEGATION_VALIDATION"

    event = find_event(app_events, "delegation_validation_failed")
    assert event.agent == "facilitator"


async def test_upstream_exhaustion_emits_retry_exhausted_event(
    pool, settings, artifact, app_events
):
    class UnreachableFacilitator(ScriptedFacilitator):
        async def invoke(self, request, *, deadline):
            raise AgentTransportError("all transport attempts exhausted")

    client = dialogue_client(pool, settings, artifact)
    session = await create_session_with(client, UnreachableFacilitator([]))

    response = await post_turn(client, session["session_id"])
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"

    event = find_event(app_events, "retry_exhausted")
    assert event.agent == "facilitator"
    assert event.error_code == "UPSTREAM_UNAVAILABLE"
