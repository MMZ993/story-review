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

## Increment 3 — Agent Engine deploys (2026-09-12/13, COMPLETE — all four agents SMOKE PASS)

Owner approved tier-2 deploys + smokes in chat. Session 1: business
reviewer, engineering reviewer, synthesis deployed and **SMOKE PASS**;
facilitator deployed through eight iterations of runtime fixes — the last
(NullPool fix) deployed as engine `7953752766122295296` but not yet
smoked at pause.

### Session 2 (2026-09-13) — facilitator root-caused, fixed, SMOKE PASS

Four more deploy iterations, each root-caused from Cloud Logging
(`resource.type="aiplatform.googleapis.com/ReasoningEngine"`; the raw
REST `:query` endpoint surfaces the container's error body where the
SDK's `Error Details` is empty):

1. `7953752766122295296`: leftover `_ENGINES[key] = engine` line in
   `_cloudsql_iam_engine` (dead reference from the NullPool rewrite) →
   NameError on every session-service call. Removed.
2. `2202656041970171904`: **connector 1.22 async API misuse — the real
   bug behind every prior "hang"**: `await connector.connect(...)` runs
   the *sync* connect path (blocking `future.result()`) on the caller's
   event loop and deadlocks it forever. Async drivers must use
   `await connector.connect_async(...)`.
3. `7899709570593849344`: IAM asyncpg connect needs an explicit `user`
   ("password authentication failed for user \"default\""), and Agent
   Engine's attached compute credentials report
   `service_account_email == "default"` — the real SA email is resolved
   from the metadata server (`.../instance/service-accounts/default/email`,
   off-loop via `asyncio.to_thread`; `CLOUDSQL_IAM_USER` env override for
   local repros).
4. `7215162427233533952`: **SMOKE PASS** (session
   `c90cb00b-c217-460e-9a1e-d7ee6d33f334`, FacilitatorTurnOutput
   validated). `7344922391497146368`: PASS as well (list_sessions
   verified over `:query`; earlier TypeError there was a bad probe
   payload — `app_name` must not be passed in the input, the AE template
   injects its own).
5. Post-review restructure (see review below) redeployed as
   `5457914147628908544` (`facilitator-7d1b9bd-dirty`): **SMOKE PASS**
   (session `2409510d-…`, auto-deleted by the new smoke cleanup).

**Persistence verified**: the Cloud SQL `facilitator` DB holds the ADK
`DatabaseSessionService` tables (`sessions`, `events`, `app_states`,
`user_states`, `adk_internal_metadata`, owner `sa-facilitator@$PROJECT_ID.iam`);
`list_sessions` over `:query` returned both smoke sessions — including
one created by a *previous* engine (persistence across engine versions,
D24 amendment 1 proven). Both smoke sessions then deleted; the final
smoke cleans up after itself.

### What was built (uncommitted working tree)

- `shared/agent_kit/agent_kit/ae_runtime.py` + tests (**agent-kit 111**,
  baseline 104→+7): `parse_cloudsql_iam_uri`, `cloudsql_iam_session_service`
  (ADK service-registry factory), `_cloudsql_iam_engine` (Cloud SQL async
  connector, IAM auth, SQLAlchemy asyncpg seam), `_IdTokenAuth` +
  `id_token_httpx_client_factory` (audience-scoped refreshing ID tokens),
  `build_root_agent` / `build_facilitator_root_agent`.
- `deploy/agents/`: `common.sh` (staging helpers), per-agent `deploy.sh` +
  thin `agent_src/` AE entry packages (`root_agent`), facilitator
  `agent_src/sitecustomize.py` (session-service registration — see
  gotchas), `smoke.py` (impersonates sa-orchestration — the runtime
  invoker; builds schema-valid inputs via the agent_kit renderers and
  validates replies with the strict shared schemas, `model_validate_json`).
- Makefile: `agents-deploy-{facilitator,business-reviewer,
  engineering-reviewer,synthesis}`.
- Terraform applied (two reviewed plans): `roles/cloudsql.client` for all
  four IAM-login SAs (connector/proxy needs `cloudsql.instances.connect`,
  which instanceUser lacks) and `roles/aiplatform.user` for the four agent
  runtime SAs (deployed containers call Vertex for every model request).
- Databases: `orchestration` (increment 2) and `facilitator` (admin-bootstrap,
  granted to `"sa-facilitator@$PROJECT_ID.iam"`).

### Deployed resources (display name `<slug>-7d1b9bd`)

| Agent | Engine id | Smoke |
|---|---|---|
| business-reviewer | `207561407045042176` | **PASS** (ReviewReport, 6 findings, real Vertex) |
| engineering-reviewer | `8786074272255705088` | **PASS** (ReviewReport, 4 findings) |
| synthesis | `669180368850518016` | **PASS** (SynthesisReport, 1 finding) |
| facilitator | `5457914147628908544` (`-dirty`, current) | **PASS** (FacilitatorTurnOutput, invoke=none; sessions persist in Cloud SQL `facilitator`) |

N-1 facilitator good engine: `7344922391497146368` (retain per D5 until
the versioning proof). Broken facilitator engines to prune later
(owner-run destructive, with the D5 pruning at increment 7):
`7503392803385245696` (hyphen module name), `4702153835160797184`
(same, pre-IAM-fix), `994846916904747008`, `1407770707739279360`,
`5295784561043570688` (services.py not loaded), `2062200028591554560`,
`2499049192446492672`, `9208005262344978432`, `6019456726166667264`,
`3157419162972717056` (iteration chain), `4044628289564704768`
(persistent-engine event-loop bug), `7953752766122295296` (`_ENGINES`
NameError), `2202656041970171904` (sync-connect deadlock),
`7899709570593849344` (missing IAM user), `7215162427233533952`
(superseded, smoke PASS).

Smoke command (repo root, `source infra/envs/home.env`):
`RESOURCE=projects/$PROJECT_ID/locations/$REGION/reasoningEngines/<id> uv
run --no-project --with google-cloud-aiplatform --with-editable
shared/review_schemas --with-editable shared/agent_kit python
deploy/agents/smoke.py <slug>`.

### Gotchas learned (ADK 2.8.0 Agent Engine runtime)

- Staged agent dir name must be a valid module name AND must not collide
  with the staged agent package (`business-reviewer` hyphen + `from
  business_reviewer import …` self-import) — staged as `<pkg>_ae`.
- `--extra_packages` (underscore flag name); adk CLI needs
  `--with google-cloud-aiplatform` in the invoking uv env (vertexai import).
- `adk api_server` loads `services.py` only from the agents dir
  (/app/agents) which an extra package cannot populate ("conflicting
  name: agents") — **registration happens via `sitecustomize.py`** (auto-
  imported from PYTHONPATH=/app before the CLI resolves the session URI).
- Agent runtime SAs need `roles/aiplatform.user` (403
  `resourcemanager.projects.get` otherwise).
- Facilitator image requirements must include `mcp` (McpToolset import;
  the base image installs only `google-adk[a2a]`), `sqlalchemy[asyncio]`,
  `greenlet`, `cloud-sql-python-connector==1.22.0`, `asyncpg`.
- connector 1.22: async API is `create_async_connector(...)`, not
  `AsyncConnector` — **and async drivers must use `connect_async`**:
  `await connector.connect(...)` is the sync path (blocking
  `future.result()`) and deadlocks the caller's event loop; IAM asyncpg
  also needs an explicit `user`, and AE compute credentials report
  `service_account_email == "default"` → resolve the real email from
  the metadata server. A per-call connector must be `close_async()`d
  (its aiohttp session must not outlive the request loop).
- The SDK surfaces AE runtime errors with an empty "Error Details"; the
  raw `:query` REST endpoint returns the container's actual error body
  (fast diagnosis path). Cloud Logging shows full tracebacks only for
  unhandled 500s; handled 400s appear as a single uvicorn access line.
- `:query` payloads must not repeat `app_name` in `list_sessions` input
  — the AE template injects its own (duplicate keywords raise TypeError
  at the call boundary).
- `agents_deploy` refuses dirty trees (`ALLOW_DIRTY_DEPLOY=1` opts in,
  label gets `-dirty`) — the version label maps resources to commits.
- SQLAlchemy asyncpg + custom `creator`: a raw coroutine creator bypasses
  the dialect adaptation ("coroutine object has no attribute await_") — the
  supported seam is `AsyncAdapt_asyncpg_dbapi.connect(async_creator_fn=…)`.
- **Agent Engine serves each request in a fresh `asyncio.run` loop**: any
  persistent async engine/session-service breaks ("is bound to a different
  event loop") — the cloudsql-iam factory is per-call: fresh engine +
  connector (NullPool — no pool_size args with NullPool) per operation,
  disposed after.
- `stream_query` requires `user_id`; strict-schema validation must use
  `model_validate_json` (dict mode rejects ISO datetime strings).
- ReasoningEngine create always yields a numeric id — versioning lives in
  `display_name` (`<slug>-<short-sha>`); the adk `--temp_folder` under our
  staging dir keeps the build context for inspection (it is still cleaned
  by the CLI on success).

### Independent review (session 2) + in-session fixes

Read-only subagent review of the full increment diff: **Needs fixes** →
all four Importants fixed in-session, minors fixed or recorded:

1. (Important) `common.sh` deploy pipeline `|| true` masked deployment
   failure — adk exit code now propagates (log written via redirect;
   grep reads the file).
2. (Important) Cloud SQL connector created per pooled connection inside
   `_connect` and never closed — `_PerCallCloudSqlSessionService._call`
   now creates one connector per operation and `close_async()`es it in
   the `finally` alongside `engine.dispose()`.
3. (Important) version label `<slug>-<sha>` lied for dirty trees —
   `agents_deploy` refuses uncommitted trees unless
   `ALLOW_DIRTY_DEPLOY=1` (label gets `-dirty`); the final facilitator
   engine is labelled `-dirty` accordingly (committed re-deploy due at
   the increment-4 smoke).
4. (Important) untested seams — `_PerCallCloudSqlSessionService` and
   `resolve_cloudsql_iam_user` extracted to module level with fake-based
   tests (lifecycle + dispose/close order, SA suffix strip, env +
   metadata fallbacks); agent-kit **117** (baseline 111).
5. (Minor) smoke leaves a facilitator session row per run — deleted in
   a `finally`; the two session-2 smoke rows also deleted via
   `:query delete_session`.
6. (Minor) dead `json.loads` in `_validate` removed.
7. (Minor) metadata fetch wrapped in `asyncio.to_thread` (loop-safe).
8. (Minor) `admin-bootstrap.py` validates `DB_NAME`/`DB_ROLE_EMAIL`
   before SQL interpolation.

Verification after fixes: agent-kit **117 passed**; final redeploy +
facilitator smoke **PASS**; persistence + cleanup verified over
`:query`.

### Session-2 admin side actions (recorded for the record)

- Local repro support: postgres role `"<owner-email>"` created in the
  `facilitator` DB + `create, usage` on schema `public` (repro of the
  IAM connect path from the main PC). Optional owner-run cleanup:
  `reassign owned tables`… not needed (role owns nothing) — simply
  `drop role "<owner-email>"` from the `facilitator` DB when no longer
  wanted.
- D24 amendment 2 recorded in local-decisions (AE-side lineage-guard
  deferral — enforcement point decided with the increment-4 invocation
  contract).
- Disposable repro assets in `/tmp`: `repro_session.py`,
  `repro_sa.py`, `repro_connect.py`, `probe_facilitator_db.py`, smoke
  logs, `/tmp/facilitator-image-test`, `/tmp/svctest`.

## Increment 2 — Cloud SQL live + migrations 0001–0005 over IAM (2026-09-12)

Owner approved tier-2 execution in chat (DB kept RUNNING at the end —
increment 3 runs in the same session and needs the facilitator session
store).

### Code changes (test-first)

- `deploy/cloud-sql/run-migrations.sh`: docker fallback now also forwards
  `PGSSLMODE` alongside the other PG* vars (Cloud SQL IAM auth requires
  TLS). Test-first: `test_docker_fallback_forwards_pgsslmode` — fake
  `docker` on PATH records `$PGSSLMODE`; no database contacted; skipped on
  hosts with a local psql (fallback not exercised there).
  Orchestration **129 passed, 12 skipped** (baseline 128+12s).
- `deploy/cloud-sql/admin-bootstrap.py` (new): one-time per-database admin
  bootstrap through the Cloud SQL Python Connector as `postgres`
  (`SPIKE_DB_PASSWORD` from `home.env`, D7 stance) — creates the unit's
  database and grants the IAM role `CREATE, USAGE` on its `public` schema
  (PG16 revokes public CREATE; IAM users get CONNECT only). Idempotent;
  parameterized (`DB_NAME`, `DB_ROLE_EMAIL`) so increment 3 reuses it for
  the facilitator database. Replaces per-spike copies of the Runbook 06
  `admin_apply.py` pattern.

### Execution + evidence (sanitized)

1. `make db-resume` → RUNNABLE after ~2.5 min (client timed out waiting on
   the patch operation; the patch had gone through). **Gotcha**: `gcloud sql
   users list` fails ~3–4 min after RUNNABLE (backend "couldn't connect to
   the database") — wait and retry; not an instance fault.
2. IAM DB users verified: `postgres` BUILT_IN + 4
   `CLOUD_IAM_SERVICE_ACCOUNT` entries (as terraform).
3. Bootstrap: `created database: orchestration` + grant to
     `"sa-orchestration@$PROJECT_ID.iam"` (connector, port 3307, admin
   password from `home.env`).
4. Migrations over IAM **as `sa-orchestration`** via the **Cloud SQL Auth
   Proxy** (see gotchas) applying 0001–0005; second run = no-op
   ("already applied" ×5). Note: no cloud identifiers in the migrated
   data (fresh empty database).
5. Verification queries (as the IAM role): 7 tables (`story_runs`,
   `sessions`, `turn_leases`, `turns`, `agent_runs`, `idempotency_claims`,
   `schema_migrations`); `one_active_run_per_story` is the 0005 per-
   `(user_id, story_id)` partial index; the role owns/has full DML on all
   7.
6. Orchestration connectivity smoke: app lifespan pool (`asyncpg` via
   `ORCH_DB_DSN`) through the proxy → `db: orchestration`, `user:
   sa-orchestration@$PROJECT_ID.iam`, `migrations: 5`.

### Terraform change (tier-2, plan shown before apply)

`infra/modules/cloud-sql/main.tf`: new `connector_clients` —
`roles/cloudsql.client` for all four IAM-login SAs. Needed because every
connector path (proxy, Python Connector, Cloud Run volume) must fetch the
ephemeral client certificate (`cloudsql.instances.connect`), which
`instanceUser` alone does not include (Runbook 06 knew this for the spike;
the grant lived in the torn-down spike module). Increment 4's Cloud Run
connector needs the same role. **Plan gotcha**: a plain `-var-file` plan
wanted to DELETE the three MCP Cloud Run services (they are gated on
`-var mcp_*_image` / `mcp_*_service_url`, per Runbook 10's two-step apply
pattern) — re-planned with the live values pulled via the v2 API (`gcloud
run services describe` v1 surface shows no image) → 4 IAM creates + 3
empty service "updates" (computed-field refresh only, `after_unknown`
empty). Applied clean; all four SAs confirmed in `roles/cloudsql.client`.

### Gotchas learned (append-worthy)

- **Empty authorized networks block raw public-IP psql**: direct
  `psql` to the instance IP:3307 fails "server closed the connection
  unexpectedly" — by design, only the proxy/language connectors are
  allowlisted. The script header's "via the Cloud SQL proxy" is the
  intended path.
- **Proxy container + port mapping**: the proxy binds 127.0.0.1 *inside*
  its container, so `-p 127.0.0.1:9031:5432` forwarding never reaches it
  ("server closed the connection"). Run it with `--network host --address
  127.0.0.1 --port 9031` instead.
- **Proxy + ADC mount**: the proxy image runs as uid 65532 and cannot read
  the owner's 0600 ADC file — run with `--user 1000:1000`.
- **Proxy + impersonation** works: `--impersonate-service-account
  sa-orchestration@…` + `--auto-iam-authn`; clients then send any dummy
  password (the proxy fetches OAuth tokens itself).
- Without `roles/cloudsql.client` the proxy 403s (`boss::NOT_AUTHORIZED …
  missing cloudsql.instances.connect`) — see terraform change above.
- `run-migrations.sh` retry wrapper masks the real psql error as "database
  not reachable" (the known deferred minor; cost ~10 min here).
- Throwaway-test-postgres readiness race: 2 more observations (one
  "test Postgres not ready", one mid-step migration failure).

Working proxy invocation (from `home.env` shell):

```bash
docker run -d --name cloudsql-proxy --network host --user 1000:1000 \
  -v ~/.config/gcloud/application_default_credentials.json:/credentials/adc.json:ro \
  gcr.io/cloud-sql-connectors/cloud-sql-proxy:2 \
  "$PROJECT_ID:$REGION:$PROJECT_ID-sessions" \
  --auto-iam-authn --address 127.0.0.1 --port 9031 \
  --impersonate-service-account=sa-orchestration@$PROJECT_ID.iam.gserviceaccount.com \
  --credentials-file=/credentials/adc.json
# then: DATABASE_URL="postgres://sa-orchestration%40$PROJECT_ID.iam:x@127.0.0.1:9031/orchestration" \
#   deploy/cloud-sql/run-migrations.sh
```

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
