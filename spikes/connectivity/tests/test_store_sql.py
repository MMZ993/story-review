"""Cloud SQL session-marker store contract tests against a fake pool.

The SQL store must satisfy the same contract as the in-memory reference
(persist-once, idempotent re-persist, defined not-found) while issuing only
parameterized statements against the `spike.session_marker` table. A fake
connection captures SQL and parameters and returns scripted rows; no
database is touched.
"""

from __future__ import annotations

import pytest

from spike_mcp.store import AlreadyStoredError, PersistSessionRequest, RestoreSessionRequest
from spike_mcp.store_sql import SqlSessionMarkerStore


class FakeConnection:
    """Records statements; replies with scripted rows per statement keyword.

    Replies are dict rows (asyncpg Record shape) or None.
    """

    def __init__(self, rows_by_keyword: dict[str, dict | None]) -> None:
        self._rows = rows_by_keyword
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql: str, *args):
        self.calls.append((sql, args))
        lowered = sql.lower()
        for keyword, row in self._rows.items():
            if keyword in lowered:
                return row
        return None


class FakeAcquire:
    """Async context manager yielding a FakeConnection (asyncpg pool shape)."""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, *exc) -> None:
        return None


class FakePool:
    """Exposes acquire() returning the asyncpg-style context manager."""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self._conn)


def _keyword(sql: str) -> str:  # pragma: no cover - helper
    raise AssertionError(f"unexpected statement: {sql}")


async def test_persist_inserts_new_marker_with_parameters() -> None:
    conn = FakeConnection({"insert": {"session_id": "s1", "marker": "m1", "correlation_id": "c1"}})
    store = SqlSessionMarkerStore(pool=FakePool(conn))

    result = await store.persist(
        PersistSessionRequest(session_id="s1", marker="m1", correlation_id="c1")
    )

    assert (result.stored, result.session_id, result.correlation_id) == (True, "s1", "c1")
    sql, params = conn.calls[0]
    assert "spike.session_marker" in sql
    assert params == ("s1", "m1", "c1")


async def test_persist_is_idempotent_for_identical_marker() -> None:
    # Same marker re-persisted: the conditional upsert returns the row.
    conn = FakeConnection({"insert": {"session_id": "s1", "marker": "m1", "correlation_id": "c2"}})
    store = SqlSessionMarkerStore(pool=FakePool(conn))

    result = await store.persist(
        PersistSessionRequest(session_id="s1", marker="m1", correlation_id="c2")
    )
    assert result.stored is True


async def test_persist_conflicting_marker_raises_already_stored() -> None:
    # Conditional upsert returns no row when a different marker exists.
    conn = FakeConnection({"insert": None})
    store = SqlSessionMarkerStore(pool=FakePool(conn))

    with pytest.raises(AlreadyStoredError):
        await store.persist(
            PersistSessionRequest(session_id="s1", marker="m2", correlation_id="c1")
        )


async def test_restore_returns_row_when_found() -> None:
    conn = FakeConnection({"select": {"marker": "m1", "correlation_id": "c1"}})
    store = SqlSessionMarkerStore(pool=FakePool(conn))

    result = await store.restore(RestoreSessionRequest(session_id="s1", correlation_id="cr"))
    assert result.found is True
    assert result.marker == "m1"
    assert result.correlation_id == "c1"
    sql, params = conn.calls[0]
    assert "spike.session_marker" in sql
    assert params == ("s1",)


async def test_restore_is_defined_not_found_for_missing_row() -> None:
    conn = FakeConnection({"select": None})
    store = SqlSessionMarkerStore(pool=FakePool(conn))

    result = await store.restore(RestoreSessionRequest(session_id="missing", correlation_id="cr"))
    assert result.found is False
    assert result.marker is None
