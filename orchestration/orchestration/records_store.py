"""Durable-record persistence: story runs, sessions, turns, agent runs
(docs/design/schemas.md "Durable Cloud SQL records").

Thin asyncpg storage over the migration-created tables — no ORM. Nested
Pydantic values (delegation, resolutions, artifact references) round-trip
through jsonb; all schema validation stays in the shared record models, so
a row is written only after its record validates and reads rebuild the same
record (equality-tested in tests).

Constraint failures surface as ConstraintViolation for the API layer to map
(e.g. second active run per story -> 409).
"""

from __future__ import annotations

import json

import asyncpg

from review_schemas.facilitator import DelegationDecision, ResolutionItem
from review_schemas.records import (
    AgentRunRecord,
    SessionRecord,
    StoryRunRecord,
    TurnRecord,
)
from review_schemas.synthesis import ArtifactReference

from .errors import ConstraintViolation


async def _insert(pool: asyncpg.Pool, sql: str, *args) -> None:
    """Run an insert, translating constraint violations to the domain error."""
    async with pool.acquire() as conn:
        try:
            await conn.execute(sql, *args)
        except asyncpg.PostgresError as exc:
            # 23xxx = integrity constraint violation class (unique, check, FK).
            if exc.sqlstate and exc.sqlstate.startswith("23"):
                raise ConstraintViolation(str(exc)) from exc
            raise


async def _fetchrow(pool: asyncpg.Pool, sql: str, *args):
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *args)


def _dumps(value) -> str | None:
    return None if value is None else json.dumps(_jsonable(value))


def _jsonable(value):
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _refs(value: str | None) -> list[ArtifactReference]:
    return [
        ArtifactReference.model_validate_json(json.dumps(item))
        for item in json.loads(value or "[]")
    ]


# --- story runs -----------------------------------------------------------


async def create_story_run(pool: asyncpg.Pool, record: StoryRunRecord) -> None:
    await _insert(
        pool,
        "insert into story_runs (story_run_id, story_id, state, created_at, "
        "updated_at) values ($1, $2, $3, $4, $5)",
        record.story_run_id,
        record.story_id,
        record.state,
        record.created_at,
        record.updated_at,
    )


async def update_story_run_state(pool: asyncpg.Pool, record: StoryRunRecord) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "update story_runs set state = $2, updated_at = $3 "
            "where story_run_id = $1",
            record.story_run_id,
            record.state,
            record.updated_at,
        )


async def get_story_run(pool: asyncpg.Pool, story_run_id: str) -> StoryRunRecord | None:
    row = await _fetchrow(
        pool, "select * from story_runs where story_run_id = $1", story_run_id
    )
    return _story_run_from_row(row) if row else None


def _story_run_from_row(row) -> StoryRunRecord:
    return StoryRunRecord(
        story_run_id=row["story_run_id"],
        story_id=row["story_id"],
        state=row["state"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --- sessions -------------------------------------------------------------


async def create_session(pool: asyncpg.Pool, record: SessionRecord) -> None:
    """Persist the full validated session record (row equals the record)."""
    await _insert(
        pool,
        "insert into sessions (session_id, story_run_id, story_id, state, "
        "requested_formats, facilitator_turn_count, final_review_reference, "
        "report_references, created_at, updated_at) "
        "values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
        record.session_id,
        record.story_run_id,
        record.story_id,
        record.state,
        record.requested_formats,
        record.facilitator_turn_count,
        _dumps(record.final_review_reference),
        _dumps(record.report_references),
        record.created_at,
        record.updated_at,
    )


async def get_session(pool: asyncpg.Pool, session_id: str) -> SessionRecord | None:
    row = await _fetchrow(
        pool, "select * from sessions where session_id = $1", session_id
    )
    if row is None:
        return None
    return SessionRecord(
        session_id=row["session_id"],
        story_run_id=row["story_run_id"],
        story_id=row["story_id"],
        state=row["state"],
        requested_formats=list(row["requested_formats"]),
        facilitator_turn_count=row["facilitator_turn_count"],
        final_review_reference=(
            ArtifactReference.model_validate_json(row["final_review_reference"])
            if row["final_review_reference"]
            else None
        ),
        report_references=_refs(row["report_references"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --- turns ----------------------------------------------------------------


async def create_turn(pool: asyncpg.Pool, record: TurnRecord) -> None:
    await _insert(
        pool,
        "insert into turns (session_id, turn_number, correlation_id, state, "
        "po_message, po_accepted, facilitator_reply, delegation, resolutions, "
        "outcome, produced_artifacts, created_at, completed_at) "
        "values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)",
        record.session_id,
        record.turn_number,
        record.correlation_id,
        record.state,
        record.po_message,
        record.po_accepted,
        record.facilitator_reply,
        _dumps(record.delegation),
        _dumps(record.resolutions),
        record.outcome,
        _dumps(record.produced_artifacts),
        record.created_at,
        record.completed_at,
    )


async def get_turn(
    pool: asyncpg.Pool, session_id: str, turn_number: int
) -> TurnRecord | None:
    row = await _fetchrow(
        pool,
        "select * from turns where session_id = $1 and turn_number = $2",
        session_id,
        turn_number,
    )
    if row is None:
        return None
    return TurnRecord(
        session_id=row["session_id"],
        turn_number=row["turn_number"],
        correlation_id=row["correlation_id"],
        state=row["state"],
        po_message=row["po_message"],
        po_accepted=row["po_accepted"],
        facilitator_reply=row["facilitator_reply"],
        delegation=(
            DelegationDecision.model_validate_json(row["delegation"])
            if row["delegation"]
            else None
        ),
        resolutions=[
            ResolutionItem.model_validate(item)
            for item in json.loads(row["resolutions"])
        ],
        outcome=row["outcome"],
        produced_artifacts=_refs(row["produced_artifacts"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


# --- agent runs -----------------------------------------------------------


async def create_agent_run(pool: asyncpg.Pool, record: AgentRunRecord) -> None:
    await _insert(
        pool,
        "insert into agent_runs (agent_run_id, agent, agent_version, "
        "prompt_sha256, story_run_id, session_id, correlation_id, "
        "input_references, output_references, state, transport_attempts, "
        "corrective_reprompts, started_at, finished_at) "
        "values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)",
        record.agent_run_id,
        record.agent,
        record.agent_version,
        record.prompt_sha256,
        record.story_run_id,
        record.session_id,
        record.correlation_id,
        _dumps(record.input_references),
        _dumps(record.output_references),
        record.state,
        record.transport_attempts,
        record.corrective_reprompts,
        record.started_at,
        record.finished_at,
    )


async def get_agent_run(
    pool: asyncpg.Pool, agent_run_id: str
) -> AgentRunRecord | None:
    row = await _fetchrow(
        pool, "select * from agent_runs where agent_run_id = $1", agent_run_id
    )
    if row is None:
        return None
    return AgentRunRecord(
        agent_run_id=row["agent_run_id"],
        agent=row["agent"],
        agent_version=row["agent_version"],
        prompt_sha256=row["prompt_sha256"],
        story_run_id=row["story_run_id"],
        session_id=row["session_id"],
        correlation_id=row["correlation_id"],
        input_references=_refs(row["input_references"]),
        output_references=_refs(row["output_references"]),
        state=row["state"],
        transport_attempts=row["transport_attempts"],
        corrective_reprompts=row["corrective_reprompts"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
