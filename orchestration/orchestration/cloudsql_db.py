"""Cloud SQL IAM-authenticated record pool for the deployed service.

When ``ORCH_DB_DSN`` carries the ``cloudsql-iam:///<connection-name>/
<database>`` scheme (the same registry URI the deployed agents use for
their session store, D24 amendment 1), the record pool is built on the
Cloud SQL Python Connector with IAM database authentication instead of a
plain TCP DSN: no passwords, the attached service account logs in.

The inc-3 Agent Engine gotchas do not apply here in the same shape —
Cloud Run serves the app on one long-lived event loop, so one persistent
connector plus a normal asyncpg pool is the correct deployment shape:

- async drivers must go through ``connector.connect_async`` (the sync
  ``connect`` deadlocks the loop — Runbook 14 increment 3);
- IAM auth needs the explicit ``user``; attached compute credentials
  report ``service_account_email == "default"``, so the real email is
  resolved from the metadata server. The user is stable for the service
  lifetime and therefore resolved once at startup (off-loop, so a broken
  IAM setup fails the lifespan rather than a mid-request connect);
  ``CLOUDSQL_IAM_USER`` env override for local repros, mirroring
  ``agent_kit.ae_runtime.resolve_cloudsql_iam_user`` (kept local because
  the orchestration image does not ship agent_kit);
- the connector is closed together with the pool. ``asyncpg.Pool`` uses
  ``__slots__``, so its ``close`` cannot be monkeypatched — the pool is
  wrapped (``CloudSqlPool``), delegating everything but close/terminate.

Connections carry an IAM token minted at creation; the pool recycles
idle connections well inside the ~1 h token lifetime
(``max_inactive_connection_lifetime``), and any connection that dies on
an expired token is transparently replaced with a fresh connect.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

import asyncpg

CLOUDSQL_IAM_SCHEME = "cloudsql-iam"

#: Idle-connection recycling bound (seconds): below the ~1 h IAM token
#: lifetime so a pooled connection never outlives its token at rest.
MAX_INACTIVE_CONNECTION_LIFETIME = 1800.0


def parse_cloudsql_iam_uri(uri: str) -> tuple[str, str]:
    """Split a ``cloudsql-iam:///<connection-name>/<database>`` DSN into
    (connection name, database name).

    The connection name (``project:region:instance``) contains colons, so
    it travels in the path, never the netloc — a non-empty netloc is
    rejected. Raises ValueError on a malformed URI — the service fails
    fast at startup rather than mid-request.
    """
    parts = urlsplit(uri)
    if parts.scheme != CLOUDSQL_IAM_SCHEME:
        raise ValueError(f"unsupported cloudsql-iam DSN scheme: {parts.scheme!r}")
    if parts.netloc:
        raise ValueError("cloudsql-iam DSN must carry an empty netloc")
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) != 2:
        raise ValueError(
            "expected cloudsql-iam:///<project>:<region>:<instance>/<database>"
        )
    return segments[0], segments[1]


def resolve_iam_user(creds, env: dict | None = None, metadata_fetch=None) -> str:
    """Cloud SQL IAM login name of the effective principal.

    Attached compute credentials report ``service_account_email ==
    "default"``; the real email comes from the metadata server. An
    explicit ``CLOUDSQL_IAM_USER`` (env) wins. Service-account emails
    drop the ``.gserviceaccount.com`` suffix per the Cloud SQL
    convention (the resulting ``<name>@<project>.iam`` login is the one
    Cloud SQL provisions).
    """
    import os

    env = env if env is not None else os.environ
    user = getattr(creds, "service_account_email", None)
    if not user or user == "default":
        user = env.get("CLOUDSQL_IAM_USER", "")
        if not user:
            if metadata_fetch is None:
                import urllib.request

                def metadata_fetch():  # noqa: F811
                    req = urllib.request.Request(
                        "http://metadata.google.internal/computeMetadata/v1/"
                        "instance/service-accounts/default/email",
                        headers={"Metadata-Flavor": "Google"},
                    )
                    return (
                        urllib.request.urlopen(req, timeout=10)
                        .read()
                        .decode()
                        .strip()
                    )

            user = metadata_fetch().strip()
    return user.removesuffix(".gserviceaccount.com")


def default_credentials():
    """Ambient ADC (attached service account on Cloud Run); injectable
    seam for deterministic tests. Blocking — never call on the loop."""
    import google.auth

    return google.auth.default()


def create_async_connector(**kwargs):
    """Cloud SQL async connector factory; injectable seam for tests."""
    from google.cloud.sql.connector import create_async_connector as factory

    return factory(**kwargs)


class CloudSqlPool:
    """asyncpg pool facade whose close/terminate also close the
    connector it was built on.

    ``asyncpg.Pool`` uses ``__slots__`` (its ``close`` cannot be
    replaced), and ``create_pool`` has no pool-class seam — so every
    attribute except the two lifecycle methods delegates to the wrapped
    pool. Callers treat it as the pool they already use (acquire, fetch,
    execute, …).
    """

    def __init__(self, pool: asyncpg.Pool, connector):
        self._pool = pool
        self._connector = connector

    def __getattr__(self, name):
        return getattr(self._pool, name)

    async def close(self) -> None:
        await self._pool.close()
        await self._connector.close_async()

    async def terminate(self) -> None:
        self._pool.terminate()
        await self._connector.close_async()


async def open_cloudsql_pool(uri: str) -> CloudSqlPool:
    """Open the orchestration record pool on Cloud SQL via the connector.

    One connector (IAM auth) backs an asyncpg pool whose every connection
    goes through ``connect_async`` (token minted per connection). The IAM
    user is resolved once, before the pool is built — off-loop, so a
    broken IAM setup fails startup, not the first request. Migrations
    must be applied first (same contract as the plain-DSN path).
    """
    connection_name, database = parse_cloudsql_iam_uri(uri)
    # google.auth.default() and the metadata fallback both block.
    creds, _ = await asyncio.to_thread(default_credentials)
    user = await asyncio.to_thread(resolve_iam_user, creds)
    connector = await create_async_connector(enable_iam_auth=True)

    async def _connect(*args, **kwargs) -> asyncpg.Connection:
        # asyncpg's Pool calls the connect callable with its own arguments
        # (the dsn positionally, plus loop/connection_class kwargs) — none
        # of them apply: every connection parameter comes from the
        # connector + the resolved IAM user.
        return await connector.connect_async(
            connection_name, "asyncpg", db=database, user=user
        )

    pool = await asyncpg.create_pool(
        min_size=1,
        max_size=8,
        max_inactive_connection_lifetime=MAX_INACTIVE_CONNECTION_LIFETIME,
        connect=_connect,
    )
    return CloudSqlPool(pool, connector)
