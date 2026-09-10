"""Session turn-lease primitive (observability.md "Turn leases and
finalization").

One lease row per session, TTL 6 minutes (one minute longer than the HTTP
deadline). Acquired with the idempotent operation claim, renewed/released
only by its lease-token holder; a crashed holder simply expires. Contention
raises SessionLocked with retry_after_seconds — the rejected caller never
owned the lease.

retry_after_seconds is computed inside Postgres so only the database clock
is involved; a row that disappears between the failed upsert and the read
(holder released concurrently) is retried rather than crashing.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import asyncpg

from .errors import SessionLocked

TTL = timedelta(minutes=6)

_ACQUIRE_SQL = """
insert into turn_leases (session_id, lease_token, acquired_at, expires_at)
values ($1, $2, now(), now() + $3::interval)
on conflict (session_id) do update
set lease_token = excluded.lease_token,
    acquired_at = excluded.acquired_at,
    expires_at = excluded.expires_at
where turn_leases.expires_at <= now()
returning lease_token
"""

_RETRY_AFTER_SQL = """
select ceil(extract(epoch from expires_at - now()))::int as retry_after
from turn_leases where session_id = $1
"""


async def _attempt_acquire(
    conn: asyncpg.Connection, session_id: str
) -> uuid.UUID | int | None:
    """One acquisition attempt.

    Returns the new lease token on success, a positive retry_after_seconds
    while another unexpired holder keeps the lease, or None when the row
    vanished mid-attempt (holder released) and the caller should retry.
    """
    token = uuid.uuid4()
    acquired = await conn.fetchval(_ACQUIRE_SQL, session_id, token, TTL)
    if acquired is not None:
        return token
    retry_after = await conn.fetchval(_RETRY_AFTER_SQL, session_id)
    return None if retry_after is None else max(1, retry_after)


async def acquire(pool: asyncpg.Pool, session_id: str) -> uuid.UUID:
    """Acquire or take over the session's turn lease.

    Returns the new lease token. An unexpired lease held elsewhere raises
    SessionLocked(retry_after_seconds); an expired lease is taken over and
    the old holder's token stops working.
    """
    async with pool.acquire() as conn:
        for _ in range(3):
            result = await _attempt_acquire(conn, session_id)
            if isinstance(result, uuid.UUID):
                return result
            if result is not None:
                raise SessionLocked(result)
    raise SessionLocked(1)  # release race persisted; caller retries with a new key


async def renew(pool: asyncpg.Pool, session_id: str, token: uuid.UUID) -> bool:
    """Extend the lease by TTL; true only for the current token holder."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "update turn_leases set expires_at = now() + $3::interval "
            "where session_id = $1 and lease_token = $2 returning session_id",
            session_id,
            token,
            TTL,
        ) is not None


async def release(pool: asyncpg.Pool, session_id: str, token: uuid.UUID) -> bool:
    """Drop the lease row; true only for the current token holder."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "delete from turn_leases where session_id = $1 and lease_token = $2 "
            "returning session_id",
            session_id,
            token,
        ) is not None
