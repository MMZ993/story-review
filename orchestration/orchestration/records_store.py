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

from review_schemas.facilitator import (
    DelegationDecision,
    IssueDraft,
    ResolutionItem,
)
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
                raise ConstraintViolation(
                    str(exc), getattr(exc, "constraint_name", None)
                ) from exc
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


async def create_story_run_or_get(
    pool: asyncpg.Pool, record: StoryRunRecord
) -> StoryRunRecord:
    """Insert-or-reuse for flow replay convergence.

    A same-id conflict (idempotent-key replay of a partially completed
    flow) returns the existing row; the one-active-run-per-story partial
    index still raises ConstraintViolation (constraint name preserved)
    for the API layer to map to STORY_SESSION_ACTIVE.
    """
    try:
        await create_story_run(pool, record)
        return record
    except ConstraintViolation:
        existing = await get_story_run(pool, record.story_run_id)
        if existing is not None and existing.story_id == record.story_id:
            return existing
        raise


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


async def create_session_or_get(
    pool: asyncpg.Pool, record: SessionRecord
) -> SessionRecord:
    """Insert-or-reuse: a same-run conflict on idempotent replay returns
    the persisted session (exactly one session per story run)."""
    try:
        await create_session(pool, record)
        return record
    except ConstraintViolation:
        existing = await _fetchrow(
            pool, "select * from sessions where story_run_id = $1",
            record.story_run_id,
        )
        if existing is not None:
            return _session_from_row(existing)
        raise


def _session_from_row(row) -> SessionRecord:
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


async def get_session(pool: asyncpg.Pool, session_id: str) -> SessionRecord | None:
    row = await _fetchrow(
        pool, "select * from sessions where session_id = $1", session_id
    )
    if row is None:
        return None
    return _session_from_row(row)


async def list_sessions(
    pool: asyncpg.Pool,
    *,
    limit: int,
    before: tuple[object, str] | None = None,
) -> tuple[list[tuple[SessionRecord, str | None]], bool]:
    """One keyset page ordered by (updated_at desc, session_id desc).

    `before` is the previous page's last (updated_at datetime, session_id)
    key; returns the page (record + advisory processing stage, exposed on
    SessionSummary for polling clients) and whether more rows follow it.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from sessions "
            "where (updated_at, session_id) < ($1::timestamptz, $2::text) "
            "or $1::timestamptz is null "
            "order by updated_at desc, session_id desc limit $3",
            before[0] if before else None,
            before[1] if before else None,
            limit + 1,
        )
    more = len(rows) > limit
    page = [
        (_session_from_row(row), row["processing_stage"])
        for row in rows[:limit]
    ]
    return page, more


async def touch_session(pool: asyncpg.Pool, session_id: str) -> None:
    """Bump updated_at (pagination freshness after a persisted turn)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "update sessions set updated_at = now() where session_id = $1",
            session_id,
        )


async def set_processing_stage(
    pool: asyncpg.Pool, session_id: str, stage: str | None
) -> None:
    """Set or clear the advisory processing-stage marker (Item F): the
    running flow's own position in the pipeline, exposed through
    SessionSummary/SessionDetail so a client may poll honest progress
    while its synchronous POST is outstanding. Cleared (None) on
    completion and on failure."""
    async with pool.acquire() as conn:
        await conn.execute(
            "update sessions set processing_stage = $2 "
            "where session_id = $1",
            session_id,
            stage,
        )


async def get_processing_stage(
    pool: asyncpg.Pool, session_id: str
) -> str | None:
    """Read the advisory stage marker (read paths for polling clients)."""
    row = await _fetchrow(
        pool, "select processing_stage from sessions where session_id = $1", session_id
    )
    return row["processing_stage"] if row else None


async def update_session(
    pool: asyncpg.Pool,
    session_id: str,
    *,
    state: str | None = None,
    facilitator_turn_count: int | None = None,
    final_review_reference=None,
    report_references: list | None = None,
    conn: asyncpg.Connection | None = None,
) -> None:
    """Apply a session-state transition (park / finalizing / completed
    with its persisted references) and the facilitator-turn count; bumps
    updated_at. `conn` joins an outer transaction (atomic transitions +
    idempotency completion).

    Terminal states (parked / completed) transition the session's story
    run in the same statement batch, keeping the one-active-run-per-story
    partial index in step with the session: a parked/completed session
    must release its story for a new run (api-contract.md: new sessions
    may use the same story)."""
    assignments = ["updated_at = now()"]
    args: list = [session_id]
    if state is not None:
        args.append(state)
        assignments.append(f"state = ${len(args)}")
    if facilitator_turn_count is not None:
        args.append(facilitator_turn_count)
        assignments.append(f"facilitator_turn_count = ${len(args)}")
    if final_review_reference is not None:
        args.append(_dumps(final_review_reference))
        assignments.append(f"final_review_reference = ${len(args)}")
    if report_references is not None:
        args.append(_dumps(report_references))
        assignments.append(f"report_references = ${len(args)}")
    executor = conn
    if executor is None:
        async with pool.acquire() as borrowed:
            await borrowed.execute(
                f"update sessions set {', '.join(assignments)} "
                "where session_id = $1",
                *args,
            )
            if state in ("parked", "completed"):
                await _retire_story_run(borrowed, session_id, state)
        return
    await executor.execute(
        f"update sessions set {', '.join(assignments)} "
        "where session_id = $1",
        *args,
    )
    if state in ("parked", "completed"):
        await _retire_story_run(executor, session_id, state)


async def _retire_story_run(
    conn: asyncpg.Connection, session_id: str, state: str
) -> None:
    """Move the session's story run to the same terminal state, releasing
    the story for a new run. Runs on the caller's connection so it joins
    the surrounding session-transition transaction."""
    await conn.execute(
        "update story_runs set state = $2, updated_at = now() "
        "where story_run_id = "
        "(select story_run_id from sessions where session_id = $1)",
        session_id,
        state,
    )


# --- turns ----------------------------------------------------------------


async def create_turn(pool: asyncpg.Pool, record: TurnRecord) -> None:
    await _insert(
        pool,
        "insert into turns (session_id, turn_number, correlation_id, state, "
        "po_message, po_accepted, facilitator_reply, delegation_rationale_reply, "
        "delegation, resolutions, new_issues, outcome, produced_artifacts, "
        "created_at, completed_at) "
        "values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)",
        record.session_id,
        record.turn_number,
        record.correlation_id,
        record.state,
        record.po_message,
        record.po_accepted,
        record.facilitator_reply,
        record.delegation_rationale_reply,
        _dumps(record.delegation),
        _dumps(record.resolutions),
        _dumps(record.new_issues),
        record.outcome,
        _dumps(record.produced_artifacts),
        record.created_at,
        record.completed_at,
    )


async def create_turn_or_get(
    pool: asyncpg.Pool, record: TurnRecord
) -> TurnRecord:
    """Insert-or-reuse: exactly one TurnRecord per (session, turn number);
    replay convergence returns the persisted authoritative record."""
    try:
        await create_turn(pool, record)
        return record
    except ConstraintViolation:
        existing = await get_turn(pool, record.session_id, record.turn_number)
        if existing is not None:
            return existing
        raise


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
    return _turn_from_row(row)


def _turn_from_row(row) -> TurnRecord:
    return TurnRecord(
        session_id=row["session_id"],
        turn_number=row["turn_number"],
        correlation_id=row["correlation_id"],
        state=row["state"],
        po_message=row["po_message"],
        po_accepted=row["po_accepted"],
        facilitator_reply=row["facilitator_reply"],
        delegation_rationale_reply=row["delegation_rationale_reply"],
        delegation=(
            DelegationDecision.model_validate_json(row["delegation"])
            if row["delegation"]
            else None
        ),
        resolutions=[
            ResolutionItem.model_validate(item)
            for item in json.loads(row["resolutions"])
        ],
        new_issues=[
            IssueDraft.model_validate(item)
            for item in json.loads(row["new_issues"] or "[]")
        ],
        outcome=row["outcome"],
        produced_artifacts=_refs(row["produced_artifacts"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


async def list_turns(
    pool: asyncpg.Pool, session_id: str
) -> list[TurnRecord]:
    """All turns of a session, ordered by turn number (history replay)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from turns where session_id = $1 order by turn_number",
            session_id,
        )
    return [_turn_from_row(row) for row in rows]


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


async def create_agent_run_or_get(
    pool: asyncpg.Pool, record: AgentRunRecord
) -> AgentRunRecord:
    """Insert-or-reuse for replay convergence (deterministic agent-run ids)."""
    try:
        await create_agent_run(pool, record)
        return record
    except ConstraintViolation:
        existing = await get_agent_run(pool, record.agent_run_id)
        if existing is not None:
            return existing
        raise


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
