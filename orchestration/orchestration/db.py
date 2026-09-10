"""Database pool lifecycle (increment 2: the app owns a pool).

create_pool on app startup from settings.db_dsn, closed on shutdown;
tests and the lifespan-free ASGI tier inject an existing pool instead.
"""

from __future__ import annotations

import asyncpg


async def open_pool(dsn: str) -> asyncpg.Pool:
    """Open the orchestration record pool (migrations must be applied)."""
    return await asyncpg.create_pool(dsn, min_size=1, max_size=8)
