"""Idempotency-claim primitive tests: replay, key reuse, crash recovery,
and route/session scoping per docs/design/schemas.md (database constraints)
and observability.md (idempotent operation claim)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from orchestration.idempotency import (
    ClaimOutcome,
    claim,
    complete,
)

ROUTE = "POST /api/v1/sessions"


def _key() -> uuid.UUID:
    return uuid.uuid4()


def _fingerprint(body: dict[str, Any]) -> str:
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def test_replay_returns_stored_canonical_response(pool):
    key = _key()
    body = {"story_id": "story-07", "requested_formats": ["md"]}

    first = await claim(pool, ROUTE, "", key, _fingerprint(body))
    assert first.outcome is ClaimOutcome.CLAIMED

    await complete(pool, ROUTE, "", key, {"session_id": "sess-x"})

    replay = await claim(pool, ROUTE, "", key, _fingerprint(body))
    assert replay.outcome is ClaimOutcome.REPLAY
    assert replay.canonical_response == {"session_id": "sess-x"}


async def test_same_key_different_body_raises_key_reused(pool):
    from orchestration.errors import IdempotencyKeyReused

    key = _key()
    await claim(pool, ROUTE, "", key, _fingerprint({"story_id": "story-07"}))

    with pytest.raises(IdempotencyKeyReused):
        await claim(pool, ROUTE, "", key, _fingerprint({"story_id": "story-08"}))


async def test_in_progress_claim_is_reported_for_crash_recovery(pool):
    """A crashed holder leaves a recoverable in-progress row (D15-4):
    a concurrent/duplicate request sees it instead of claiming twice."""
    key = _key()
    fingerprint = _fingerprint({"story_id": "story-07"})

    await claim(pool, ROUTE, "", key, fingerprint)
    duplicate = await claim(pool, ROUTE, "", key, fingerprint)

    assert duplicate.outcome is ClaimOutcome.IN_PROGRESS
    assert duplicate.canonical_response is None


async def test_keys_are_scoped_per_route_and_session(pool):
    key = _key()
    fingerprint = _fingerprint({"message": "hello"})

    assert (
        await claim(pool, "POST /api/v1/sessions/s1/turns", "s1", key, fingerprint)
    ).outcome is ClaimOutcome.CLAIMED
    # Same key on a different route or a different session claims cleanly.
    assert (
        await claim(pool, "POST /api/v1/sessions/s2/turns", "s2", key, fingerprint)
    ).outcome is ClaimOutcome.CLAIMED
    assert (
        await claim(pool, "POST /api/v1/sessions/s1/finalize", "s1", key, fingerprint)
    ).outcome is ClaimOutcome.CLAIMED
