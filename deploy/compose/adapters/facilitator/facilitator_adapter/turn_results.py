"""Postgres-backed turn-result store for the facilitator adapter.

One row per completed (session_id, invocation_id) in the same Postgres
that backs the ADK `DatabaseSessionService` (FACILITATOR_DB_URL) — the
local shape of the Agent Engine reconciliation seam (D15-6,
observability.md "Turn leases and finalization"). Adapter-owned runtime
state: created idempotently on startup, outside the orchestration
migrations.
"""

from __future__ import annotations

import uuid

import asyncpg

from agent_kit.facilitator_input import FacilitatorResponse

_TABLE_SQL = """
create table if not exists facilitator_turn_results (
    session_id    text not null,
    invocation_id uuid not null,
    response      jsonb not null,
    created_at    timestamptz not null default now(),
    primary key (session_id, invocation_id)
)
"""


class PostgresTurnResultStore:
    """Durable at-most-once facilitator results in the session backend."""

    def __init__(self, dsn: str):
        # compose supplies the ADK DatabaseSessionService DSN form
        # (`postgresql+asyncpg://...`); asyncpg wants the bare scheme.
        self._dsn = dsn.replace("postgresql+asyncpg", "postgresql", 1)
        self._pool: asyncpg.Pool | None = None

    async def startup(self) -> None:
        """Open the pool and ensure the table exists (idempotent)."""
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
        async with self._pool.acquire() as conn:
            await conn.execute(_TABLE_SQL)

    async def shutdown(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def save(
        self, session_id: str, invocation_id: uuid.UUID, response: FacilitatorResponse
    ) -> None:
        assert self._pool is not None, "startup() must run first"
        async with self._pool.acquire() as conn:
            await conn.execute(
                "insert into facilitator_turn_results "
                "(session_id, invocation_id, response) values ($1, $2, $3) "
                "on conflict (session_id, invocation_id) do nothing",
                session_id,
                invocation_id,
                response.model_dump_json(),
            )

    async def lookup(
        self, session_id: str, invocation_id: uuid.UUID
    ) -> FacilitatorResponse | None:
        assert self._pool is not None, "startup() must run first"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "select response from facilitator_turn_results "
                "where session_id = $1 and invocation_id = $2",
                session_id,
                invocation_id,
            )
        if row is None:
            return None
        return FacilitatorResponse.model_validate_json(row["response"])
