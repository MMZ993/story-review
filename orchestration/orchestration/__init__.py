"""Orchestration service package (Phase 6).

FastAPI orchestration per docs/design/api-contract.md and data-flow.md.
Increment 0 ships configuration, durable-record persistence (asyncpg, no
ORM), and the idempotency-claim / turn-lease primitives.
"""
