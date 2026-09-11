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

## Increment 1 — MCP client wrapper + stories endpoints + real /health (2026-09-13)

Local Docker only (throwaway Postgres + compose `local` stack); no cloud
actions; Cloud SQL STOPPED throughout.

What was implemented (per plan increment 1):

- `orchestration/mcp_client.py`: direct MCP client wrapper over the `mcp`
  SDK (streamable HTTP, one initialize+call session per attempt). Policy per
  observability.md: 60 s short-call timeout / 3 attempts, half-jittered
  backoff on 1 s/2 s bases, retry only on connection/timeout or retryable
  tool codes (`UPSTREAM_UNAVAILABLE`, `RENDER_FAILED`); never on 4xx-class
  tool errors. Remaining-deadline clamping to `min(short-call timeout,
  remaining − 5 s cleanup reserve)`; an attempt that cannot fit is never
  started (`DeadlineExceededError` before any transport call). Injectable
  `session_call` seam (`tool=None` = initialize-only probe for /health).
- `orchestration/stories.py`: `GET /api/v1/stories` (proxy `list_stories`,
  orchestration-side case-insensitive title filter — the MCP `filter` is a
  status filter, so the API title filter is applied here) and
  `GET /api/v1/stories/{story_id}` (proxy `get_story`); 404
  `STORY_NOT_FOUND` / retryable 503 envelopes; upstream payload-validation
  failures also map to 503.
- `orchestration/api_errors.py` + `main.py`: `ApiError` → shared
  `ErrorEnvelope` handler, `RequestValidationError` → 422 `VALIDATION_ERROR`
  envelope (contract: no free-form `detail`), correlation-ID middleware
  (echo/mint; malformed supplied UUIDs are replaced, never surfaced as 500).
- `orchestration/health.py` + real `/health`: concurrent single-probe
  reachability flags for story/artifact/report, `ok`/`degraded`
  (`HealthResponse`). DB flag deferred to increment 2 (app owns a pool then).
- Makefile `orchestration-stack-test` (env-gated compose-stack gate, the
  Phase 5 live-test convention); `mcp==2.1.1` added to both orchestration
  requirement sets (client version aligned with the contract suite; locks
  recompiled).

Verification (commands = `make orchestration-stack-test` /
`make orchestration-test` / `make review-schemas-test` /
`docker build -q -f orchestration/Dockerfile .`):

- orchestration **43 passed** with `ORCH_TEST_STORY_URL` set (38
  deterministic + 5 stack tests against the real compose story MCP); plain
  target **38 passed, 5 skipped**.
- review-schemas **154** (baseline unchanged).
- Docker image builds (new mcp dependency included).

Independent read-only review (fresh subagent, snapshot `/tmp/pi-review.*`):
**Ready to proceed**. Important fixed in-session: malformed client
`X-Correlation-Id` caused an unenveloped 500 on error paths — middleware now
validates and mints a replacement (+ regression test). Minors fixed
in-session: probe docstring (initialize-only, not list_tools);
`health_probe_timeout_seconds` setting added (was hardcoded); non-404 tool
errors now honor `error.retryable` for the retry hint instead of always
retryable.

Gotchas learned:

- `mcp==2.1.1` `streamable_http_client` yields **2** values `(read, write)`,
  not 3 — the 3-tuple unpack is a newer SDK API.
- The streamable client wraps exceptions raised inside the session in a
  (possibly nested) `ExceptionGroup` on teardown; the wrapper unwraps to the
  first leaf via `except*` + `_first_leaf` before retry classification.
- Strict `ErrorBody` requires a `uuid.UUID` instance for `correlation_id`
  (JSON string round-trip needs explicit coercion when parsing tool errors).
- `run-migrations.sh`'s docker fallback can hit a startup race ("server
  closed the connection unexpectedly") on the first psql contact after
  `pg_isready` succeeds — a retry clears it (observed twice). Candidate
  small fix next increment.

Increment 1 verdict: **green**. Next: increment 2 (flow 1 — session
creation + browse/history read paths; live gate on main PC).

## Increment 2 — flow 1: session creation + read paths (2026-09-13)

Local Docker only (throwaway Postgres; compose stack not required for the
deterministic tier); no cloud actions; Cloud SQL STOPPED throughout.

What was implemented (per plan increment 2):

- `orchestration/agent_clients.py`: frozen Phase 5 adapter-contract mirrors
  (ReviewerInvocation / SynthesisInvocation / FacilitatorInvocation +
  result dataclasses — orchestration cannot import agent_kit without the
  ADK) and the policy-wrapped HTTP clients: short calls 60 s / 3 attempts
  with half-jittered 1 s / 2 s backoff (reviewers, synthesis), facilitator
  120 s / 2 attempts with fixed 5 s backoff; retry only on connection /
  timeout / retryable 5xx envelope (malformed 5xx bodies count as
  retryable); 4xx-class envelopes never retried; per-attempt timeout
  clamped to the remaining deadline minus the 5 s reserve; backoff is not
  slept past the point where the next attempt cannot fit.
- `orchestration/flows.py` (flow 1): idempotency claim → `get_story` →
  deterministic story_run/session ids → story-artifact save → parallel
  reviewer fan-out (sibling cancelled on first failure) → review saves +
  AgentRunRecords → synthesis (both perspective pairs) → save + record →
  session record → facilitator opening turn (turn-1 invariants asserted:
  `invoke=none`, no resolutions → structured 422 `DELEGATION_VALIDATION`)
  → TurnRecord → canonical `CreateSessionResponse` persisted + 201.
  Crash/replay convergence: `story_run_id`, `session_id`, `agent_run_id`
  derived by uuid5 from the client Idempotency-Key (the `run-`/`sess-`
  patterns pin only lowercase hex), the same key reused for every
  `save_artifact` (dedup scope is (run, type, key)), and insert-or-get on
  every durable row; an in_progress claim left by a crashed holder is
  taken over (convergent re-run).
- `orchestration/sessions_api.py`: `POST /api/v1/sessions` (Idempotency-Key
  header required, UUID v4 enforced → 422), `GET /api/v1/sessions`
  (keyset pagination on (updated_at desc, session_id desc), opaque base64
  cursor; naive cursor timestamps → 422), `GET
  /api/v1/sessions/{session_id}` (SessionDetail: turns + server-side
  artifact fetch via `list_artifacts`; unknown session 404;
  `*_NOT_FOUND` tool errors map 404).
- `orchestration/db.py` + main.py: app-owned asyncpg pool (lifespan;
  injectable for tests), `/health` gains the database flag (deferred from
  increment 1).
- records_store: `ConstraintViolation.constraint` preserved;
  insert-or-get for story run (active-run conflict still raises for
  `STORY_SESSION_ACTIVE` 409), session, turn, agent run; `list_sessions`
  keyset query; `list_turns`; `touch_session`.
- config: 4 mandatory adapter URLs (`ORCH_{BUSINESS,ENGINEERING,SYNTHESIS,
  FACILITATOR}_URL`); runtime requirements gain `httpx` (locks recompiled).
- Tests: `tests/fakes.py` (in-process fake agent clients + an
  artifact-MCP seam fake with real dedup/versioning semantics),
  `test_agent_clients.py` (transport policy), `test_create_session_flow.py`
  (success + durable state, replay side-effect-free, partial-failure
  recovery via key replay, crashed in_progress takeover, active-session
  409, key-reuse 409, unknown story 404, missing key 422, delegating
  opening turn 422, non-v4 key 422, synthesis/facilitator input assembly),
  `test_sessions_read.py` (list order/limit/cursor, detail, 404, bad limit,
  naive cursor 422), `test_flow1_live.py` (env-gated live gate).
- Makefile `orchestration-flow1-live-test` (throwaway Postgres + compose
  stack env; needs `make agents-compose-up`).

Verification (commands = `make orchestration-test` / `make
review-schemas-test` / `docker build -q -f orchestration/Dockerfile .`):

- orchestration **59 passed, 6 skipped** (5 stack tests without compose +
  the live gate) — deterministic tier incl. the new flow/read tests.
- review-schemas **154** (baseline unchanged); Docker image builds.
- Live gate (main PC): **PASS** — `make agents-compose-up` (stack healthy
  on 8101–8114) + flow-1 live run: one real session creation on story-07
  over compose HTTP with real Vertex calls — 201 with a schema-valid
  `CreateSessionResponse`, 4 `AgentRunRecord`s, detail/list read paths
  verified, and a same-key replay returning the stored canonical response
  (1 passed in 79.63 s ≈ 4 model calls, trial credits).

Independent read-only review (fresh subagent, snapshot `/tmp/pi-review.*`):
**Needs fixes first** → all fixes applied in-session, re-verified green:

- Important: naive cursor datetime could escape as an unenveloped 500 →
  timezone-aware check → 422 (+ regression test); opening-turn
  `invoke=none` now asserted in orchestration (structured 422, not a
  pydantic 500) (+ test); synthesis AgentRunRecord input_references now
  list both perspective references (per-run input/output reference
  lists); malformed adapter 5xx bodies are retryable, not terminal.
- Important (reviewer could not locate the deterministic flow tests in the
  snapshot — they exist as `tests/test_create_session_flow.py` /
  `test_sessions_read.py`, all green).
- Minors fixed: fan-out sibling cancellation; backoff deadline clamp;
  Idempotency-Key UUID v4 enforcement; `*_NOT_FOUND` → 404 in
  `_run_artifacts`; dead test code removed.
- Live-gate fixes (found only against the real adapters): HTTP clients
  posted to the adapter base URL without the `/invoke` / `/turn` route
  (404 → malformed-body 503), and adapter response payloads with JSON
  string datetimes must be parsed via `model_validate_json` (nested
  `SynthesisReport.inputs` references) — the deterministic tier could
  not catch either (fakes hand over Python objects); both fixed and the
  deterministic suite re-run green.

Deferred minors (recorded): mirror models weaker than the frozen agent_kit
validators (add facilitator turn/message agreement when increment 3
assembles turn inputs); AgentRunRecord started/finished timing fidelity
(stamp before invoke when increment 3 generalizes recording); facilitator
run output_references = synthesis reference (produces no artifact);
opening-turn ADK-session duplication in the crash window is tolerated
(model cost, never state) — increment 3's invocation-ID reconciliation
must cover the opening turn too.

Gotchas learned:

- Strict-mode models reject JSON string datetimes: every payload crossing
  the MCP/JSON seam must go through `model_validate_json(json.dumps(...))`
  — same rule as increment 0's jsonb round-trips, now also on the
  replay path (canonical response) and adapter error envelopes
  (correlation_id needs explicit UUID coercion).
- asyncpg binds `$1::timestamptz` only from tz-aware datetimes — cursor
  decoding must validate tzinfo or a DataError 500 escapes.
- Row-value keyset pagination direction: next page rows are strictly
  *smaller* than the cursor key — `(updated_at, session_id) < ($1, $2)`.
- reviewer AgentRunRecords reference the session FK — the session row must
  be inserted before any agent-run persistence.
- run-migrations.sh docker-fallback startup race observed twice more
  (4 observations total; new variant: "database system is starting up"
  after pg_isready) — the small-retry fix is now clearly due before
  Phase 8; retries cleared it each time.

Increment 2 verdict: **green** — deterministic tier 59 passed / 6
skipped; live gate PASS. Next: increment 3 (flow 2 — dialogue turns).

## Increment 3 — flow 2: dialogue turns + reconciliation seam (2026-09-13)

Scope per plan + D15 amendment 1 (owner-approved in chat):

- **Adapter contract extension (option A)**: `FacilitatorRequest.invocation_id`
  (required), adapter-side at-most-once result persistence per
  `(session_id, invocation_id)` in `facilitator_turn_results` (Postgres
  session backend, adapter-owned, `create table if not exists` at startup),
  `POST /turn` replay returns the stored result without a model run,
  `GET /turn-result/{session_id}/{invocation_id}` 200/404 reconciliation
  endpoint. `agent_kit` got `TurnResultStore` (protocol + in-memory) and a
  store-driven app lifespan; the binding layer supplies
  `PostgresTurnResultStore` (asyncpg).
- **Orchestration flow 2** (`turns_flow.py` + `turn_execution.py` +
  `lineage.py` + `turns_api.py`): lease → idempotency claim (scoped
  route+session) → lineage-scoped input assembly → facilitator invocation
  with deterministic invocation id (uuid5 of the idempotency key) →
  TurnRecord with stamped resolutions → delegation execution (both /
  business / engineering with previous review + extra context, parallel
  with sibling cancellation; reuse_previous / none skip reviewers) →
  at-most-once synthesis per turn (latest-per-perspective pairing) → gate
  precedence (park at facilitator turn 10 → continue-on-new-synthesis →
  open-issues-empty+none finalize) → single TurnResponse; canonical
  `CanonicalTurnResult` replay (resolutions re-read from the TurnRecord).
- **Increment-3 finalize gap (option B)**: gate-finalize and `po_accepted`
  return retryable 503 `UPSTREAM_UNAVAILABLE` (increment 4 wires flow 3);
  no turn state persisted; claim stays in_progress.
- Client: `HttpFacilitatorClient` reconciles between attempts via
  `/turn-result` (best-effort GET, 10 s budget); reviewers/synthesis
  unchanged.

Commands (deterministic tier, all via existing targets):

```
make orchestration-test        # 76 passed / 7 skipped (baseline 59+6s; live gate skips)
make agent-kit-test            # 86 passed (baseline 82; +4 reconciliation tests)
make facilitator-adapter-test  # 3 passed / 1 skipped (binding now exercises /turn + /turn-result)
make review-schemas-test       # 154 (unchanged)
make agents-test               # 4x4 (unchanged)
docker compose --profile local --profile local-agents build facilitator-adapter  # image ok
docker build -f orchestration/Dockerfile .                                        # image ok
```

Evidence: deterministic tier green first run after implementation fixes
(strict-JSON parse for artifact content — same gotcha family as increment 2;
`CanonicalTurnResult` has no `resolutions` field, so replays re-read the
TurnRecord). Live gate: **pending** — run
`make orchestration-turns-live-test` (needs `agents-compose-up`, main PC,
real Vertex; ~5 model calls incl. flow 1) with owner approval.

Gotchas learned:

- FastAPI/Starlette here has no `add_event_handler`; the result store is
  wired through an app lifespan in `agent_kit` instead.
- `ErrorBody`'s retryable⇔hint invariant forces `SESSION_LOCKED` to be
  `retryable=true` + `retry_after_seconds`; the "new request, not the same
  turn" rule lives in the code-specific client behavior (D15 amdt 1 item 3).
- `GetArtifactInput` requires both `artifact_id` and `story_run_id`.

### Increment 3 review + fixes + live gate (session 36)

Independent read-only subagent review of the increment diff: verdict
**Needs fixes before proceeding** → all findings fixed in-session:

- **Critical**: shared-client `_reconcile_target` instance state on
  `HttpFacilitatorClient` could cross sessions under concurrency — the
  reconcile target is now a request-scoped closure threaded through
  `_call(recover=...)`; the mutable `_deadline` was removed the same way
  (backoff now receives `deadline_at`).
- **Important**: a same-key retry of the turn that parked the session got
  a permanent 409 SESSION_READ_ONLY — REPLAY is now served before the
  read-only rejection, and the park transition + idempotency completion
  are one DB transaction (`update_session`/`idempotency.complete` gained
  optional `conn`), closing the crash window between parked state and
  stored canonical response. New test: park-turn same-key replay 200.
- **Important**: flow 2 persisted no facilitator AgentRunRecord — added
  (input refs = synthesis + evidence, output = synthesis, per flow 1).
- Minors fixed: reconcile test now covers miss-then-hit sequencing; new
  gate test parks at facilitator turn 10 even when a synthesis was
  produced (precedence 2 > 3); `turns_api` reuses
  `flows.map_idempotency_reused`; adapter `POST /turn` documents the
  concurrent-duplicate caveat (at-most-once storage, not work).

Re-verification after fixes: orchestration **77 passed / 7 skipped**
(+2), agent-kit 86, facilitator adapter 3+1s, review-schemas 154, agents
skeleton 4×4, both images rebuilt.

Live gate (owner approved in chat; `make agents-compose-up` then
`make orchestration-turns-live-test`): **PASS** — 1 passed in 127 s.
Real session creation (story-07) + one real dialogue turn (re-review
message) over compose HTTP incl. real Vertex: 200 schema-valid
TurnResponse (turn 2, outcome continue), turn record + facilitator count
asserted in Postgres, same-key replay returned the identical canonical
response, history read path served turns [1, 2]. ≈5 model calls.

Live-only gotchas fixed in-session:

- `FACILITATOR_DB_URL` in compose is the ADK/SQLAlchemy form
  (`postgresql+asyncpg://…`) — `PostgresTurnResultStore` now normalizes
  the scheme for asyncpg (first live run failed adapter startup with
  `invalid DSN: … got 'postgresql+asyncpg'`).
- throwaway-postgres startup race observed once more during test runs
  (5 observations total; the small-retry fix in run-migrations.sh stays
  due before Phase 8).

Increment 3 verdict: **green** — deterministic tier 77+7s; live gate
PASS. Next: increment 4 (flows 3+4 — finalization, reports, PO
acceptance), which also removes the two documented increment-3 finalize
gaps.

## Increment 4 — flows 3+4: finalization, reports, PO acceptance (session 37)

Scope per plan + D15 amendment 2 (signed-URL settlement, below):

- **Flow 3 core** (`finalization.py`): session → `finalizing` (idempotent
  retry marker) → deterministic `finalized-review` artifact (latest
  synthesis + dialogue resolutions aggregated latest-per-issue + PO
  acceptance state; `remaining_open_issues` retained only on explicit
  acceptance) → `render_report` per requested format (idempotent per
  (run, format)) → one transaction: report references + `completed` +
  canonical response (schemas.md completed invariants). Retryable
  failures keep `finalizing` and release the lock; non-retryable
  failures (deterministic `RENDER_FAILED`, validation, malformed render
  output) roll back to `active` — no session stuck in `finalizing`.
- **Flow 2 wiring**: the two increment-3 503 gaps removed. Gate-finalize
  continues synchronously into flow 3 under the same lease;
  `po_accepted` turns bypass facilitator/delegation, take the next
  chronological turn number, never increment
  `facilitator_turn_count`, and finalize in the same TurnResponse.
  Facilitator count is durable from the finalize turn record onward
  (crash-window safety).
- **Endpoints** (`finalize_api.py`): `POST /sessions/{id}/finalize`
  four-state table (finalizing → lease + resume flow 3 + atomic
  completion; completed → read-only fresh URLs, no writes; active → 409
  `NOT_FINALIZING`; parked → 409 `SESSION_READ_ONLY`); session re-read
  under the lease closes the finalize-vs-completed race.
  `GET /sessions/{id}/report`: completed only, fresh signed URLs, 409
  `REPORT_NOT_READY` otherwise. Completed `SessionDetail` now exposes
  `reports` (fresh URLs).
- **Same-key retry semantics**: a retry of a turn whose flow 3 failed
  retryably resumes flow 3 directly (no facilitator, no duplicate turn
  record) via the in-progress claim; a rejected new key's claim row is
  released (`idempotency.release`) so it can never masquerade as a
  legitimate takeover; parked/completed/finalizing sessions reject new
  turn keys with 409.
- **Signed URLs** (`signed_urls.py`): V4-signed HTTPS download URLs via
  google-cloud-storage from the report server's deterministic object
  layout (`runs/<run>/reports/<id>.<ext>`); URLs never stored (regenerated
  on every read/replay). See D15 amendment 2.

Commands (deterministic tier + regression):

```
make orchestration-test        # 90 passed / 8 skipped (baseline 77+7s; +1 live skip)
make review-schemas-test       # 154 (unchanged)
make agent-kit-test            # 86 (unchanged)
make facilitator-adapter-test  # 3+1s (unchanged)
make agents-test               # 4x4 (unchanged)
make compose-contract-test     # 20 (unchanged; fake-gcs dual-scheme wiring)
docker build -f orchestration/Dockerfile .   # image ok (key file rides in the package dir)
```

Evidence: deterministic tier green; review findings (4 Important + 6
minors from the independent read-only review) fixed in-session and
re-verified by a focused re-review (**Ready to proceed**); throwaway
postgres startup race observed once (6 total; fix stays due before
Phase 8).

D15-5 empirical verification (standalone throwaway fake-gcs container,
then the recomposed stack): `-scheme both -backend memory
-public-host 127.0.0.1:<https-port>` serves the shared memory backend on
HTTPS (container 4443 → host `${FAKE_GCS_HTTPS_PORT:-9026}`) and HTTP
(container 8000 → host `${FAKE_GCS_PORT:-9025}`); the
`/bucket/object?X-Goog-Signature=…` path serves bytes over HTTPS with no
signature validation. Compose wiring updated: artifact/report servers and
gcs-init use `http://fake-gcs:8000`; contract tests keep
`http://127.0.0.1:9025`.

Live gate (owner approved in chat; `make orchestration-finalize-live-test`):
**PASS** — 1 passed in 63 s. Real session creation (story-07, md+pdf)
over compose HTTP incl. real Vertex, then an explicit `po_accepted`
turn finalizing synchronously in the same 200 TurnResponse (report
entries for both formats, facilitator_turn_count still 1), durable
completed session row with both report references, GET /report fresh
URLs, and real report-byte downloads from fake-gcs over the signed
HTTPS URLs (TLS verification relaxed locally). ≈4 model calls.

Live-only gotchas fixed in-session:

- The compose stack had gone down between verification and the gate
  (all services exited); `agents-compose-up` brought it back.
- `test_flow1_live._live_env()` filters the environment to
  `REQUIRED_ENV`, silently dropping `ORCH_LIVE_GCS_PUBLIC_URL` — the
  live fixture read it from `os.environ` directly; without it the
  signer fell back to ambient-ADC mode and failed (user tokens cannot
  sign V4 URLs).
- asyncpg returns jsonb columns as strings — `len(row)` on a jsonb
  string is its character length, not its element count.
- Throwaway-postgres startup race observed twice more during the gate
  runs (8 observations total; the small-retry fix in run-migrations.sh
  stays due before Phase 8).

Gotchas learned:

- `ReportDownload.signed_url` is `HttpsUrl` (strict `^https://`), so the
  planned "unsigned HTTP fake-gcs URL" fallback was impossible;
  fake-gcs's dual-scheme mode (HTTPS on `-port`, HTTP on `-port-http`)
  satisfies the schema and keeps the internal HTTP paths untouched.
- Same strict-JSON datetime gotcha family as increments 2/3:
  `RenderReportOutput` must round-trip through
  `model_validate_json(json.dumps(raw))`.
- A single scripted retryable `render_report` failure is swallowed by
  the client's 3-attempt retry policy — failure scripting must exhaust
  the policy (3 entries) to reach the 503 path.

## Increment 5 — exit gate: live integration suite + phase close (session 38)

Design (D15 amendment 3): `orchestration/tests/integration/` — fully live
over the compose stack (real MCP servers + four agent adapters + real
Vertex; throwaway migrated Postgres), run via
`make orchestration-integration-test`. Model-dependent behavior is
steered through the PO message and asserted on observable outcomes
only; scripted truth-table coverage stays in the deterministic tier.

- `conftest.py` — shared live fixture (full app, real McpClients +
  default agent set, ASGI HTTP; `ORCH_LIVE_GCS_PUBLIC_URL` read from
  `os.environ` directly — the increment-4 gotcha).
- `helpers.py` — env gate (`live_env`), fresh v4 keys, flow-1/flow-2
  request helpers.
- `test_flow_arc_live.py` (story-07, md+pdf): flows 1–4 arc — creation,
  same-key replay (identical), key-reuse different body 409
  `IDEMPOTENCY_KEY_REUSED`, second active session 409
  `STORY_SESSION_ACTIVE`, detail + keyset pagination reads, re-review
  dialogue turn 2 + its same-key replay, steered gate finalize (bounded
  4-attempt loop) → completed with both report references, report-byte
  downloads over the signed fake-gcs HTTPS URLs, completed-session
  finalize-endpoint replay (fresh URLs, no writes), GET /report, and
  read-only 409 afterwards.
- `test_park_at_ten_live.py` (story-05): steering-kept-open dialogue
  turns 2–9 `continue`, turn 10 `park`/`parked`; parked session is
  read-only (turn 409 `SESSION_READ_ONLY`, finalize 409, history
  readable).
- `test_lease_contention_live.py` (story-06): slow delegating turn in
  flight; concurrent fresh-key turn rejected 409 `SESSION_LOCKED` with
  `retry_after_seconds >= 1` before any work; only turn 2 durable
  afterwards.

Commands:

```
make orchestration-test               # 90 passed / 11 skipped (3 new live skips)
make orchestration-integration-test   # live gate (below)
```

Live gate (owner approved the full-live scope in chat): **PASS** —
`make orchestration-integration-test`: **3 passed in 366.95 s**. All
three scenarios green in one run: flows 1–4 arc (creation, replays,
key-reuse/active-session 409s, reads, re-review turn + replay, steered
gate finalize on the first steering turn → completed with md+pdf report
references, report-byte downloads over signed fake-gcs HTTPS, finalize
endpoint replay, GET /report, read-only 409), park-at-10 (turns 2–9
continue under steering, turn 10 parked, read-only enforcement), lease
contention (concurrent fresh-key turn 409 SESSION_LOCKED with retry
hint while the delegating turn was in flight; only turn 2 durable).

Regression suites after increment 5: orchestration 90+11s (3 new live
skips collected in the plain run); review-schemas 154; agent-kit 86;
business 6+2s; engineering 7+1s; synthesis 7+2s; facilitator 3+1s;
compose contract 20. Phase-close review: see below.

Gotchas learned:

- **Two live iterations failed on test-side assumptions, not service
  bugs** (both fixed before the passing run): (1) with exactly one
  session, `next_cursor` is null (no more rows) and httpx serializes
  `params={"cursor": None}` as an **empty string** `cursor=`, which
  `ShortText` (min_length 1) correctly rejects → 422 "invalid limit or
  cursor"; the test now follows the cursor only when non-null. (2) the
  completed-session finalize replay regenerates **fresh** signed URLs
  by design, so replay bodies are not byte-identical (expires_at
  differs); the test now compares durable references/formats instead.
- Throwaway-postgres startup race observed once more (9 observations
  total; first gate attempt died on "test Postgres not ready", clean
  retry); the small-retry fix in run-migrations.sh stays due before
  Phase 8 cloud runs.
- The steered gate finalize fired on the **first** steering turn both
  runs — the facilitator prompt's contract-based output (open_issues,
  invoke) is reliably steerable through the PO message.
- Gate runtime ≈ 6 minutes for all three scenarios (~35–40 model
  calls), well inside the D15-amendment-3 estimate.

### Phase-close review (session 38)

Independent read-only subagent review of the phase diff (9aaa45a..worktree,
focus on increment 5 + phase coherence against the plan exit criteria and
api-contract/data-flow/schemas): **Ready to close** — no Critical or
Important findings. Coverage table confirmed all six exit criteria
covered across the live suite + deterministic tier + increment gates.
Minors fixed in-session:

- M1: the plan's literal increment-5 scope lists "PO-acceptance path"
  among the suite items; the suite's `post_turn` helper always sends
  `po_accepted=false`. **PO-acceptance live coverage lives in the
  increment-4 gate** (`tests/test_finalize_live.py`, session 37 PASS) —
  recorded here as the explicit home of that coverage rather than
  duplicating the arc in the exit-gate suite.
- M2: lease-contention test now documents its 2 s timing assumption
  (in-process lease acquisition; premature completion would fail loudly).
- M3 (not fixed, harmless): the live fixture does not close the asyncpg
  pool if client setup fails before yield — throwaway container only.
