"""Idempotency-claim primitive (D15-4, schemas.md database constraints).

Every mutating request stores its idempotency key, request fingerprint, and
canonical logical response as a DB claim row written with the lease
acquisition: in_progress at claim time, completed with the stored canonical
response. A crashed holder leaves a recoverable in_progress row; replays
return the stored response; a different body with the same key raises
IdempotencyKeyReused.

Keys are scoped per route + session ('' marks session-less routes).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

import asyncpg

from .errors import IdempotencyKeyReused


class ClaimOutcome(Enum):
    """What a claim() call found."""

    CLAIMED = "claimed"  # we own it; run the operation, then complete()
    REPLAY = "replay"  # completed earlier; return canonical_response
    IN_PROGRESS = "in_progress"  # another/crashed holder is mid-operation


@dataclass(frozen=True)
class ClaimResult:
    outcome: ClaimOutcome
    canonical_response: dict[str, Any] | None = None


async def claim(
    pool: asyncpg.Pool,
    route: str,
    session_id: str,
    key: Any,
    request_fingerprint: str,
) -> ClaimResult:
    """Claim the (route, session, key) idempotency slot for a request body.

    Raises IdempotencyKeyReused when the key was already used with a
    different fingerprint.
    """
    async with pool.acquire() as conn:
        inserted = await conn.fetchrow(
            """
            insert into idempotency_claims
                (route, session_id, idempotency_key, request_fingerprint,
                 state, created_at, updated_at)
            values ($1, $2, $3, $4, 'in_progress', now(), now())
            on conflict (route, session_id, idempotency_key) do nothing
            returning state, request_fingerprint, canonical_response
            """,
            route,
            session_id,
            key,
            request_fingerprint,
        )
        if inserted is not None:
            return ClaimResult(ClaimOutcome.CLAIMED)

        existing = await conn.fetchrow(
            """
            select request_fingerprint, state, canonical_response
            from idempotency_claims
            where route = $1 and session_id = $2 and idempotency_key = $3
            """,
            route,
            session_id,
            key,
        )
    if existing["request_fingerprint"] != request_fingerprint:
        raise IdempotencyKeyReused(
            f"idempotency key already used with a different request body: {key}"
        )
    if existing["state"] == "completed":
        response = (
            json.loads(existing["canonical_response"])
            if existing["canonical_response"] is not None
            else None
        )
        return ClaimResult(ClaimOutcome.REPLAY, response)
    return ClaimResult(ClaimOutcome.IN_PROGRESS)


async def complete(
    pool: asyncpg.Pool,
    route: str,
    session_id: str,
    key: Any,
    canonical_response: dict[str, Any],
) -> None:
    """Store the canonical logical response and mark the claim completed."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            update idempotency_claims
            set state = 'completed', canonical_response = $4::jsonb,
                updated_at = now()
            where route = $1 and session_id = $2 and idempotency_key = $3
            """,
            route,
            session_id,
            key,
            _json(canonical_response),
        )


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value)
