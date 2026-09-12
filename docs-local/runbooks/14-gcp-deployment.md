# Runbook 14 — GCP deployment & versioning proof (Phase 8)

Plan: `docs-local/plans/phase-8-gcp-deployment.md`. Decisions: D24 (+
D5/D17 dependencies). All cloud actions follow infra-rules: read-only is
agent-runnable; tier-2 (writes) owner-approved; destructive actions are
owner-run only. Evidence sanitized (`$PROJECT_ID`, placeholders) —
identifier check before any commit containing evidence.

## Increment 0 — decisions, plan, deploy-script fixes (2026-09-21)

D24 + the plan were recorded in the planning session; this session
delivered the two deferred `deploy/cloud-sql/run-migrations.sh` fixes
(Runbook 12/13 deferred minors):

1. **No credentialed DSN in argv** — `DATABASE_URL` is parsed once into
   libpq's `PG*` environment (`dsn_to_pg_env`, python3 `urllib.parse`,
   percent-decoded; query parameters rejected). The docker fallback
   forwards only the set vars (`-e PGHOST …`) so no connection
   parameter ever appears in a process argv (`ps` on a shared host
   leaks nothing). The script is now sourceable (main guarded by
   `BASH_SOURCE == $0`) so the parser is unit-testable.
2. **First-contact retry** — the schema_migrations bootstrap contact is
   retried (`MIGRATION_CONTACT_RETRIES`, default 10 × 1 s; env
   overridable) to cover the observed startup race (pg_isready passing
   before the server accepts sessions). Later SQL failures still fail
   fast.

Tests: `orchestration/tests/test_run_migrations.py` — DSN parsing
(components, decoding, defaults, query-param rejection) + full-script
run through a `psql` wrapper that fails if any argument looks like a
DSN or the PG* env is missing, plus a second-run no-op assertion
(skipped on hosts without a local psql — this machine has none, so the
Makefile target itself exercises the docker fallback: observed
"psql not found; using throwaway postgres:16 container" then
"migrations up to date").

Verification: `make orchestration-test` green (see increment 1).

## Increment 1 — user scoping (2026-09-21)

Docs (api-contract X-User-Id section, schemas user_id records +
per-(user, story) constraint) were applied in the planning session
(`8ad3570`); this session implemented against them.

### What changed

- **review-schemas 0.9.0 → 0.10.0**: `UserId` base type (UUID v4);
  `user_id` on `StoryRunRecord`/`SessionRecord` (+2 tests, install test
  bumped).
- **Migration `0005_user_scoping.sql`**: `user_id uuid not null` on
  `story_runs` + `sessions` (backfilled from story_runs); the global
  `one_active_run_per_story` index replaced by a per-`(user_id,
  story_id)` partial index **under the same constraint name**, so the
  existing 409 `STORY_SESSION_ACTIVE` mapping is unchanged. Legacy rows
  are grouped under sentinel user `00000000-0000-4000-8000-000000000000`.
- **Orchestration**: new `users.py` `require_user_id` dependency
  (missing/malformed/non-v4 → 422 VALIDATION_ERROR) on every session
  route (create/list/detail/turns/finalize/report/abandon); stories +
  health stay exempt. `records_store.get_session` is ownership-scoped
  (cross-user ids read as absent → 404) and `list_sessions` filters by
  user; the flow-1 idempotency fingerprint includes `user_id` (same
  create key replayed for another user → 409 IDEMPOTENCY_KEY_REUSED,
  never the other user's canonical response). Deterministic ids are
  unchanged (client keys are UUID v4).
- **Webui**: `/api` proxy allowlist gains `x-user-id`; new
  `static/user.js` — UUID v4 in a 90-day sliding cookie (`sr_user`,
  refreshed on every visit, malformed values replaced); `api.js`
  attaches `X-User-Id` on every call (`options.getUserId` injectable);
  `app.js` boot refreshes the cookie. No DOM → id still returned, just
  not persisted (node unit tests).

### Tests

- Orchestration `tests/test_user_scoping.py` (7): bad-header 422 table;
  two users same story → independent sessions + per-user 409; scoped
  lists; cross-user 404 on detail/turns/finalize/abandon/report with
  the owner untouched; cross-user create-key replay rejected.
- Webui: proxy forwards `X-User-Id` (pytest); `user.test.js` (8) +
  2 api-client header tests (vitest).

### Verification

- review-schemas **177** (baseline 176, +1); orchestration **127+12s**
  (baseline 116+11s; +7 scoping, +3 DSN parser, 1 psql-wrapper test
  skipped — no local psql); webui **pytest 14 + vitest 87** (baselines
  13+77; note pytest 13 was the post-presentation baseline, HANDOFF
  said 12); compose contract **20**.

### Compose migration + live gate (local stack, no cloud actions)

- Migration 0005 applied to the compose Postgres by hand (docker exec
  psql, same begin/commit + tracking-row procedure as 0003/0004):
  15 rows backfilled to the sentinel user; global index dropped and
  per-user index created.
- Stack rebuilt (`make agents-compose-up`), both images carrying the
  new code.
- **Gate PASS**: `GET /api/v1/sessions` without `X-User-Id` → 422
  VALIDATION_ERROR, with a v4 header → 200 (direct :8130); two fresh
  users created real flow-1 sessions on the same story (`story-02`)
  through the webui proxy (:8120) — both 201/active in ≈44 s each,
  distinct session ids; lists scoped (1/1); cross-user detail 404 while
  the owner reads 200; same-user second create on the story → 409
  STORY_SESSION_ACTIVE; the sentinel user lists all 15 legacy sessions.
  Both gate sessions then abandoned (parked, evidence retained).
  Note: test users used literal pattern uuids (`1111…`/`2222…`), not
  real identifiers.

### Independent review (read-only subagent)

Verdict: **Ready to proceed** — no Critical; 1 Important + minors. Scoping
audit found no cross-user leak (all routes traced through the
ownership-scoped fetch; session-scoped idempotency claims unreachable
before the ownership check). Findings and dispositions:

- **Important — fixed**: `export_pg_env`'s here-string swallowed
  `dsn_to_pg_env` failures (set -e does not trip on `$(...)` inside
  `<<<"$(...)"`), letting the script continue without PG* exports. Fixed:
  parse into a local first, `|| exit 2` on failure, empty-parse guard;
  verified `?sslmode=` and a bogus scheme now abort with rc=2.
- **Minor — fixed**: missing test that story reads work *without*
  X-User-Id (the contract exemption) — added to `test_user_scoping.py`
  (orchestration now 128).
- **Minor — accepted as-is, with reasons**: (a) migration orphan-session
  pre-check — unnecessary: `sessions.story_run_id` has an FK to
  `story_runs`, so the backfill join cannot miss; (b) cookie `secure`
  attribute — deferred to increment 5: the local compose origin is plain
  HTTP (`127.0.0.1:8120`), a `secure` cookie would break local
  development; add when serving behind the TLS domain; (c)
  `retry_first_contact` masks non-connection bootstrap errors behind the
  generic retry message; (d) migration-name string interpolation in the
  tracking insert (repo-controlled filenames). (c)+(d) recorded as
  deferred minors.
