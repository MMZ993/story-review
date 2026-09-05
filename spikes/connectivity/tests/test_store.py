"""Session-marker store contract tests.

The store is the deterministic core behind the MCP tools; the Cloud SQL proof
is an integration check, not a substitute for these tests.
"""

import pytest

from spike_mcp.store import (
    AlreadyStoredError,
    InMemorySessionMarkerStore,
    PersistSessionRequest,
    RestoreSessionRequest,
)


async def test_persist_rejects_empty_session_id() -> None:
    with pytest.raises(Exception):
        PersistSessionRequest(
            session_id="", marker="marker-1", correlation_id="corr-1"
        )


async def test_persist_rejects_empty_marker() -> None:
    with pytest.raises(Exception):
        PersistSessionRequest(
            session_id="session-1", marker="", correlation_id="corr-1"
        )


async def test_persist_rejects_empty_correlation_id() -> None:
    with pytest.raises(Exception):
        PersistSessionRequest(session_id="session-1", marker="marker-1", correlation_id="")


async def test_persist_records_marker_once() -> None:
    store = InMemorySessionMarkerStore()
    result = await store.persist(
        PersistSessionRequest(
            session_id="session-1", marker="marker-1", correlation_id="corr-1"
        )
    )
    assert result.stored is True
    assert result.session_id == "session-1"

    # A second persist with a different marker for the same session is rejected.
    with pytest.raises(AlreadyStoredError):
        await store.persist(
            PersistSessionRequest(
                session_id="session-1", marker="marker-2", correlation_id="corr-2"
            )
        )

    # Idempotent re-persist of the identical marker is accepted.
    again = await store.persist(
        PersistSessionRequest(
            session_id="session-1", marker="marker-1", correlation_id="corr-1"
        )
    )
    assert again.stored is True


async def test_restore_returns_stored_marker_for_known_session() -> None:
    store = InMemorySessionMarkerStore()
    await store.persist(
        PersistSessionRequest(
            session_id="session-1", marker="marker-1", correlation_id="corr-1"
        )
    )
    result = await store.restore(RestoreSessionRequest(session_id="session-1", correlation_id="corr-r"))
    assert result.found is True
    assert result.session_id == "session-1"
    assert result.marker == "marker-1"
    assert result.correlation_id == "corr-1"


async def test_restore_reports_defined_not_found_for_unknown_session() -> None:
    store = InMemorySessionMarkerStore()
    result = await store.restore(RestoreSessionRequest(session_id="missing", correlation_id="corr-r"))
    assert result.found is False
    assert result.session_id == "missing"
    assert result.marker is None
