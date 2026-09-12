"""Durable-record store tests: schema constraints from docs/design/schemas.md
(unique turn per (session, turn_number), one active run per story, one session
per story run) and full round-trip fidelity of the record serialization."""

from __future__ import annotations

import pytest

from orchestration import records_store
from orchestration.errors import ConstraintViolation

from . import factories


async def test_story_run_round_trip_and_active_run_uniqueness(pool):
    run = factories.story_run(story_id="story-07")
    await records_store.create_story_run(pool, run)
    assert (await records_store.get_story_run(pool, run.story_run_id)) == run

    # A second non-completed/non-parked run for the same story is rejected.
    with pytest.raises(ConstraintViolation):
        await records_store.create_story_run(pool, factories.story_run("story-07"))

    # Completing (or parking) the first run frees the story for a new run.
    completed = run.model_copy(update={"state": "completed", "updated_at": factories.now()})
    await records_store.update_story_run_state(pool, completed)
    await records_store.create_story_run(pool, factories.story_run("story-07"))


async def test_one_session_per_story_run(pool):
    run = factories.story_run()
    session = factories.session(run)
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, session)

    duplicate = session.model_copy(update={"session_id": factories.session_id()})
    with pytest.raises(ConstraintViolation):
        await records_store.create_session(pool, duplicate)


async def test_turn_unique_per_session_and_turn_number(pool):
    run = factories.story_run()
    session = factories.session(run)
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, session)

    turn = factories.turn(session, 2, with_delegation=True)
    await records_store.create_turn(pool, turn)

    with pytest.raises(ConstraintViolation):
        await records_store.create_turn(pool, factories.turn(session, 2))


async def test_turn_round_trip_preserves_nested_models(pool):
    run = factories.story_run()
    session = factories.session(run, requested_formats=["md", "pdf"])
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, session)
    turn = factories.turn(
        session, 2, with_delegation=True, delegation_rationale_reply="Why: rate limit."
    )

    await records_store.create_turn(pool, turn)
    stored = await records_store.get_turn(pool, session.session_id, 2)

    assert stored == turn
    assert stored.delegation is not None and stored.delegation.invoke == "both"
    assert stored.delegation_rationale_reply == "Why: rate limit."
    assert stored.resolutions[0].turn_number == 2
    assert stored.produced_artifacts[0].type == "synthesis"


async def test_session_round_trip(pool):
    run = factories.story_run()
    session = factories.session(run, requested_formats=["md"])
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, session)

    assert (await records_store.get_session(pool, session.session_id)) == session
    assert await records_store.get_session(pool, factories.session_id()) is None


async def test_completed_session_round_trip_including_artifacts(pool):
    """The insert writes every record field, so a completed session with a
    final review and report references round-trips exactly."""
    run = factories.story_run()
    session = factories.session(run, requested_formats=["md"])
    final_review = factories.artifact_reference(
        run.story_run_id, type_="finalized-review"
    )
    report = factories.artifact_reference(run.story_run_id, type_="report-md")
    completed = session.model_copy(
        update={
            "state": "completed",
            "facilitator_turn_count": 5,
            "final_review_reference": final_review,
            "report_references": [report],
            "updated_at": factories.now(),
        }
    )
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, completed)

    stored = await records_store.get_session(pool, session.session_id)
    assert stored == completed
    assert stored.final_review_reference == final_review
    assert stored.report_references == [report]


async def test_agent_run_round_trip(pool):
    run = factories.story_run()
    session = factories.session(run)
    await records_store.create_story_run(pool, run)
    await records_store.create_session(pool, session)
    record = factories.agent_run(session, agent="facilitator")

    await records_store.create_agent_run(pool, record)
    assert (await records_store.get_agent_run(pool, record.agent_run_id)) == record
