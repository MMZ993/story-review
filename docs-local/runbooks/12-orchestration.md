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

**Implementation (session 33, 2026-09-13, main PC; local Docker only, no cloud
actions, Cloud SQL STOPPED throughout):**

Commands run (all local; `orchestration-test` starts a throwaway
`postgres:16` on 127.0.0.1:9030, applies the real migration files via
`run-migrations.sh`, runs pytest, removes the container):

    make orchestration-test    # 19 passed
    make review-schemas-test   # 154 passed (regression baseline unchanged)
    docker build -f orchestration/Dockerfile -t orchestration-dev-test .   # ok
    docker run --rm --entrypoint sh orchestration-dev-test \
      -c 'PYTHONPATH=/app:/app/shared python -c \
      "from orchestration.main import create_app; print(create_app().title)"'
    # -> story-review orchestration (image then removed)

Delivered:
- `orchestration/` uv package 0.1.0 (D15-1): `config.py` (strict env, all
  observability.md constants), `errors.py`, `main.py` (app factory +
  `/health` scaffolding; real health flags at increment 1), `idempotency.py`
  (claim/complete, D15-4), `lease.py` (acquire/renew/release, TTL 6 min,
  conditional-update takeover), `records_store.py` (asyncpg, no ORM, D15-2),
  root-context Dockerfile (dataset guard like the MCP services), pytest.ini
  (asyncio auto), requirements.in/lock + tests/requirements.in/lock.
- `deploy/cloud-sql/migrations/0001_orchestration_records.sql` (schemas.md
  DB constraints: one-active-run-per-story partial unique index, one session
  per story run, one lease row per session, unique turn per
  (session, turn_number), idempotency PK (route, session, key), state/check
  constraints) + `run-migrations.sh` (schema_migrations tracking,
  per-file transaction, psql-or-throwaway-postgres:16-container fallback).
- Makefile `orchestration-test` target.
- Tests (19): idempotency replay/reuse/in-progress/route+session scoping;
  lease acquire/renew/release holder checks, contention → SESSION_LOCKED +
  retry_after_seconds, expired-lease takeover; record constraints + full
  round-trips incl. nested DelegationDecision/ResolutionItem/ArtifactReference
  jsonb fidelity; config strictness; /health scaffolding.

Independent read-only review (fresh subagent, snapshot `/tmp/pi-review.*`):
**Ready to proceed**, no Critical/Important. Minors fixed in-session: lease
release-race retry + DB-clock-only retry_after computation; TTL single
source (Settings derives from lease.TTL); full-fidelity session insert
(+ new completed-session round-trip test); check/FK violations mapped to
ConstraintViolation (SQLSTATE 23*); test hygiene (public factories.now(),
no-op assert removed). Minor deferred: **run-migrations.sh passes DATABASE_URL
(credentialed) in process argv — revisit before Phase 8 Cloud SQL runs**
(low risk locally; consider PGPASSWORD/env-based connection); Linux
host-network assumption of the docker fallback documented in the script.

Gotchas learned:
- Strict-mode Pydantic records round-trip through jsonb only via
  `model_validate_json` (string datetimes fail `model_validate` in strict
  mode) — records_store parses nested models accordingly.
- async tests need `asyncio_mode=auto` (orchestration/pytest.ini), unlike
  the sync MCP suites.
- postgres:16 first boot can take ~20 s; the Makefile readiness loop waits
  up to 30 s.
- httpx ASGITransport requires an AsyncClient (no sync context manager).

Increment 0 verdict: **green** (19 orchestration tests; review-schemas 154
regression unchanged; Docker image builds and imports). Next: increment 1
(MCP client wrapper + stories endpoints + real /health).
