"""Database pool lifecycle (increment 2: the app owns a pool).

create_pool on app startup from settings.db_dsn, closed on shutdown;
tests and the lifespan-free ASGI tier inject an existing pool instead.
A ``cloudsql-iam:///`` DSN (deployed service, Phase 8 increment 4)
routes to the connector-backed IAM pool in cloudsql_db.py.
"""

from __future__ import annotations

import asyncpg

from .cloudsql_db import CLOUDSQL_IAM_SCHEME


async def open_pool(dsn: str) -> asyncpg.Pool:
    """Open the orchestration record pool (migrations must be applied)."""
    if dsn.startswith(f"{CLOUDSQL_IAM_SCHEME}:///"):
        from .cloudsql_db import open_cloudsql_pool

        return await open_cloudsql_pool(dsn)
    return await asyncpg.create_pool(dsn, min_size=1, max_size=8)
