# Runbook 12 — Orchestration (FastAPI) (Phase 6)

Environment: owner's main PC (ADC + Vertex available; compose stack local). Cloud
SQL stays STOPPED throughout Phase 6 — orchestration state lives in the compose
`postgres:16` substitute with the same migration files that will run against Cloud
SQL in Phase 8. Plan: `docs-local/plans/phase-6-orchestration.md`; decisions D15
(once recorded).

Verification-state log (append-only):

## Increment 0 — packaging + persistence + idempotency/lease primitives

**Status: Decisions settled (D15, 2026-09-13); implementation NOT STARTED.**

All six increment-0 owner decisions approved in chat and recorded as **D15** in
local-decisions.md: `orchestration/` uv package + compose wiring; ordered SQL
migrations + asyncpg repository, no ORM; fake in-process agent clients for the
deterministic tier (D13 extension — LLM behavior never scripted, MCP servers
never faked, live gates main-PC only); DB idempotency claim + canonical
response; fake-gcs signed-URL emulation verified empirically at increment 4
(fallback recorded if partial); facilitator reconciliation implemented against
the local adapter's Postgres session backend, mechanism confirmed at increment 3.
