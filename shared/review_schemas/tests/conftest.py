"""Shared fixtures for the review_schemas test suite.

Only fixed (deterministic) UUID/timestamp/pattern values live here, so every
test is independent of wall-clock time or random generation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

#: Stable UUIDs usable as idempotency/correlation IDs and inside run IDs.
FIXED_UUID = UUID("12345678-90ab-4cda-b0de-1f2e3d4c5b6a")
FIXED_UUID_ALT = UUID("feedface-1234-4cda-b0de-1f2e3d4c5b6a")

#: Fixed timezone-aware UTC timestamp for model fixtures.
FIXED_TS = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)

#: Fixed ISO-8601 UTC string form of FIXED_TS for JSON-mode inputs.
FIXED_TS_JSON = "2026-09-06T12:00:00Z"

#: Fixed hyphenated UUID string used to build conforming prefixed IDs.
UUID_STR = "12345678-90ab-4cda-b0de-1f2e3d4c5b6a"

#: Conforming identifier examples (patterns from docs/design/schemas.md).
RUN_ID = f"run-{UUID_STR}"
SESSION_ID = f"sess-{UUID_STR}"
ARTIFACT_ID = f"art-{UUID_STR}"
AGENT_RUN_ID = f"arun-{UUID_STR}"


@pytest.fixture
def fixed_uuid() -> UUID:
    return FIXED_UUID


@pytest.fixture
def fixed_ts() -> datetime:
    return FIXED_TS
