"""Cloud SQL-backed session-marker store (connectivity spike).

Same contract as the in-memory reference store, backed by the
`spike.session_marker` table created by the increment-2 migration.
Connections come from an asyncpg pool over the Cloud Run-injected unix
socket `/cloudsql/<instance-connection-name>`; IAM database authentication
supplies a short-lived OAuth access token as the password (the runtime
service account is the database user, `sa-...@<project>.iam` without the
`.gserviceaccount.com` suffix — Cloud SQL convention, Runbook 06 §2).

Errors: `AlreadyStoredError` when a different marker exists for a session
(the conditional upsert returns no row). All statements are parameterized;
no identifier interpolation.
"""

from __future__ import annotations

from typing import Any, Protocol

import asyncpg

from spike_mcp.store import (
    AlreadyStoredError,
    PersistSessionRequest,
    PersistSessionResult,
    RestoreSessionRequest,
    RestoreSessionResult,
)

SOCKET_DIR = "/cloudsql"
DB_NAME = "postgres"

_PERSIST_SQL = """
INSERT INTO spike.session_marker (session_id, marker, correlation_id)
VALUES ($1, $2, $3)
ON CONFLICT (session_id) DO UPDATE
    SET correlation_id = EXCLUDED.correlation_id
    WHERE spike.session_marker.marker = EXCLUDED.marker
RETURNING session_id, marker, correlation_id
"""

_RESTORE_SQL = """
SELECT marker, correlation_id FROM spike.session_marker WHERE session_id = $1
"""

TokenProvider = Any  # async zero-arg callable returning an access token str


class _PoolLike(Protocol):
    def acquire(self) -> "asyncpg.pool.PoolAcquireContext": ...


class SqlSessionMarkerStore:
    """Session-marker store over an asyncpg pool.

    The pool is created lazily on first use so importing the module (tests)
    performs no I/O. `password_provider` is an async callable returning a
    fresh OAuth access token for IAM db auth at connect time.
    """

    def __init__(
        self,
        instance_connection_name: str | None = None,
        db_user: str | None = None,
        password_provider: TokenProvider | None = None,
        db_name: str = DB_NAME,
        pool: _PoolLike | None = None,
    ) -> None:
        self._instance_connection_name = instance_connection_name
        self._db_user = db_user
        self._db_name = db_name
        self._password_provider = password_provider
        self._pool_override = pool
        self._pool: _PoolLike | None = pool

    async def _ensure_pool(self) -> _PoolLike:
        if self._pool is None:
            if not (self._instance_connection_name and self._db_user and self._password_provider):
                raise RuntimeError(
                    "SQL store not configured: instance connection name, db user, "
                    "and password provider are required"
                )
            password = await self._password_provider()
            # Token lifetime is ~1h; the spike service is short-lived, and the
            # pool is created once per container (recorded as a spike gotcha).
            self._pool = await asyncpg.create_pool(
                host=f"{SOCKET_DIR}/{self._instance_connection_name}",
                user=self._db_user,
                password=password,
                database=self._db_name,
                min_size=1,
                max_size=2,
            )
        return self._pool

    async def _close(self) -> None:
        if self._pool is not None and self._pool_override is None:
            await self._pool.close()
            self._pool = None

    async def persist(self, request: PersistSessionRequest) -> PersistSessionResult:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _PERSIST_SQL, request.session_id, request.marker, request.correlation_id
            )
        if row is None:
            # A different marker is already stored for this session.
            raise AlreadyStoredError(request.session_id)
        return PersistSessionResult(
            stored=True,
            session_id=row["session_id"],
            correlation_id=row["correlation_id"],
        )

    async def restore(self, request: RestoreSessionRequest) -> RestoreSessionResult:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_RESTORE_SQL, request.session_id)
        if row is None:
            return RestoreSessionResult(
                found=False,
                session_id=request.session_id,
                correlation_id=request.correlation_id,
            )
        return RestoreSessionResult(
            found=True,
            session_id=request.session_id,
            marker=row["marker"],
            correlation_id=row["correlation_id"],
        )


async def access_token_provider() -> str:
    """Fetch an OAuth access token for the runtime identity (ADC/MDS)."""
    import google.auth

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/sqlservice.login"]
    )
    if not credentials.valid:
        import google.auth.transport.requests

        credentials.refresh(google.auth.transport.requests.Request())
    token = credentials.token
    if not token:  # pragma: no cover - defensive
        raise RuntimeError("no access token available for IAM db auth")
    return token


def iam_db_user(sa_email: str) -> str:
    """Map a service-account email to its IAM database username."""
    return sa_email.removesuffix(".gserviceaccount.com")
