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

## Increment 4 — orchestration Cloud Run + live CR→AE gate (2026-09-13, COMPLETE — gate PASS)

Owner approved steps 1–4 in chat ("lets do 1,2,3,4"; gate delegated to
the agent mid-run: "maybe You can do whole tests"). Cloud SQL RUNNING
throughout. All identifiers below in shell-variable/placeholder form.

### What was implemented (local, test-first)

- **Cloud SQL IAM record pool** (`orchestration/cloudsql_db.py` +
  `db.py` dispatch + `tests/test_cloudsql_db.py`): `ORCH_DB_DSN`
  accepts `cloudsql-iam:///<conn-name>/<database>` — an asyncpg pool
  (public `create_pool(connect=…)` seam, asyncpg ≥0.30) over a Cloud
  SQL async connector (`enable_iam_auth=True`, IAM user resolved once
  at startup off-loop, `CLOUDSQL_IAM_USER` env override); idle
  recycling 1800 s < 1 h IAM token; `CloudSqlPool` wrapper closes the
  connector with the pool (asyncpg Pool `__slots__` forbid patching
  `close`). `cloud-sql-python-connector[asyncpg]==1.22.0` pinned.
- **MCP ingress auth** (`id_tokens.py` + `mcp_client.py` + config):
  `ORCH_MCP_ID_TOKEN_AUTH=1` attaches audience-scoped ID-token bearer
  headers (metadata-server mint, cached to expiry − 60 s) — required by
  both the Cloud Run ingress IAM check and the mcp_ingress middleware.
- **Deploy script** `deploy/cloud-run/orchestration/deploy.sh` +
  `.env.example` (AE pointers in a gitignored `.env`): AR image build +
  push with a dirty-tree guard, `gcloud run deploy` as sa-orchestration,
  AE mode, `--add-cloudsql-instances`, `--timeout 600` (> 300 s turn
  deadline), 0–2 instances, `--no-allow-unauthenticated`.

### Live root causes found and fixed at the gate (each with a test)

1. asyncpg `Pool` calls the `connect` callable with the dsn
   **positionally** plus `loop`/`connection_class` kwargs — signature
   must be `(*args, **kwargs)`. Two deploy iterations.
2. mcp 2.1.1 `streamable_http_client()` has **no `headers` parameter**
   (TypeError, seen only as empty probes) — headers ride an injected
   caller-owned `httpx.AsyncClient(http_client=…)`, closed in `finally`.
3. **MCP ID-token audience = the service ROOT**, not the `…/mcp` route
   (same class of bug fixed on both sides: orchestration
   `main.py` and agent-kit `_audience_for`).
4. `_bearer_token` was `async def` under `asyncio.to_thread` — header
   contained a coroutine repr → 401 from the AE endpoint.
5. **Agent Engine session state lives behind the agent-runtime `:query`
   methods** (`create_session` / `list_sessions` / `get_session`), NOT
   the control-plane `/sessions` REST routes: numeric control-plane
   sessions are invisible to streamQuery (SessionNotFoundError).
   Proven live: an SDK/runtime-created session (UUID id) works, a
   control-plane one (numeric id) does not — same engine, same calls.
   `ae_client` session helpers rewritten onto `:query`.
6. `:query` wraps method returns under `"output"`.
7. agent-kit `_IdTokenAuth` must **subclass `httpx.Auth`** (isinstance
   validation — TypeError otherwise) and **refresh at mint**
   (`IDTokenCredentials.token` is None until refreshed → "Bearer None").
8. `get_session` with a `config` dict input returns zero events; without
   it the full event history comes back (what option-B reconciliation
   wants).
9. Facilitator `get_session`/`:query` eagerly opens the MCP toolsets —
   the toolset auth bugs above surfaced there first.

### Deploys (this increment)

- Facilitator clean-tree redeploys, all SMOKE PASS:
  `facilitator-a7257a3` (engine `<fac-eng-1>`), then after the
  httpx.Auth + audience + mint fixes `facilitator-3b61a75`
  (`<fac-eng-2>`) and `facilitator-dc95165` (`<fac-eng-3>`, current
  pointer). Earlier engines retained per D5 (prune list grows by 3).
- Cloud Run service `orchestration` created (region europe-west4,
  min-instances 0): ~18 revisions across the fix iterations; final
  revision healthy. Service URL contains the project number — use
  `$SERVICE_URL` in any pasted evidence.

### Gate evidence (final, all PASS)

- `GET /health` (authenticated): `{"status":"ok"}` — database
  (Cloud SQL IAM connector pool) + story/artifact/report (ID-token MCP
  calls) all reachable from Cloud Run.
- User scoping: no `X-User-Id` → 422 VALIDATION_ERROR; cross-user
  session detail → 404 while the owner reads 200.
- **Flow-1 create (all four agents via AE)**: 201 in 55–72 s on
  story-02/-03/-04/-05/-06/-07 (multiple runs across the fix
  iterations), schema-valid `CreateSessionResponse` with a real
  facilitator opening turn; ~4–6 Vertex model calls each.
- Failure-path evidence (owner-driven, pre-fix): flow-1 503 leaves the
  session active (same-key retry semantics); the stuck session was
  parked live via `POST /sessions/{id}/abandon` → 200 parked (D22 live
  on the deployed service).
- **Persistence + reconciliation read-back**: exactly ONE AE session per
  review session (userId = review session id, app `facilitator_ae`) in
  the Cloud SQL-backed runtime store; `get_session` returns the turn's
  user + facilitator events. Session-route assumption from D25
  **amended**: runtime `:query` methods, not control-plane REST.
- Read paths: session detail (turn count 1), scoped list, stories (45).
- Cleanup: control-plane probe sessions + sdk-diag runtime session
  deleted; gate review sessions + their AE sessions retained as
  evidence (per-user, harmless).

### Review (read-only subagent)

Round 1 (pool + deploy.sh): 1 Critical (`pool.close` reassignment —
asyncpg `__slots__`; fixed with the `CloudSqlPool` wrapper before any
deploy) + Importants (blocking `google.auth.default()` per connection
→ startup resolution; missing dirty-tree guard) — fixed in-session.
Round 2 (full `4d5cd59..HEAD`): **Ready to proceed**, 9 minors; 3 fixed
(connector close try/finally, pool-build-failure leak, empty IAM user
fail-loud), the rest deferred below.

### Verification

- orchestration **191+12s** (baseline 160+12s; +31 across the session);
  agent-kit **125** (baseline 122; +3 auth/audience tests); docker
  image builds; identifier check run before the wrap-up commit.

### Deferred minors (this increment)

- `_resolve_session` (`:query` create/list, 10 s, single-shot) is not
  inside the facilitator attempt loop — covered by the orchestrator-level
  retryable 503 (observed working live); acceptable.
- `_IdTokenAuth.auth_flow` refreshes only when already expired (no
  margin) vs `id_tokens`' 60 s margin.
- `id_token_httpx_client_factory` silently drops an `auth` argument.
- `_bearer_token` mints a fresh ADC token per AE round trip (no cache).
- AdkApp `:query` methods (incl. `get_session`) eagerly open the MCP
  toolsets — latency on reconciliation reads, revisit at Item D.
- Control-plane `/sessions` numeric sessions from pre-fix iterations
  were deleted; if any remain they expire on their own (1 y TTL).

## Increment 5 — webui Cloud Run + public domain (2026-09-13, deploy COMPLETE — walkthrough OPEN, one defect to fix)

Environment change first: **all work moved to the dev server** (previously
"deterministic work only"). gcloud + az CLIs installed and authed (ADC
valid; az logged in — personal account has **no Azure subscription**, so
`az account show` always nags "az login"; expected, only `az devops` used).
Gitignored env files copied from the main PC over NFS; **terraform state
copied to the dev server** (`infra/terraform.tfstate*` + `.terraform/`,
local backend) — terraform now runs here; main PC copy untouched.

Local part (test-first; committed `1d66551` + `f0a1e97`/`6310eb1` deploy.sh
fixes):
- `webui/webui/id_tokens.py` (mirrors orchestration's, single-audience):
  metadata-minted ID token for the proxy hop; `ORCHESTRATION_ID_TOKEN_AUTH`
  config flag; `/api` proxy attaches `Authorization`; mint failure → the
  existing retryable 503 envelope. Direct unit tests (`test_id_tokens.py`,
  `_fetch`/`_now` seams).
- `sr_user` cookie gains `secure` only over HTTPS (public deploy); plain-HTTP
  compose unchanged (+2 vitest).
- `deploy/cloud-run/webui/deploy.sh`: build/push, idempotent
  `run.invoker` for sa-webui on orchestration (**recorded deviation**: the
  orchestration CR service is gcloud-deployed, not terraform — the binding
  cannot live in IaC), deploy public/unauthenticated.
- Terraform: `sa-webui` in the runtime SA list. Plan (Runbook-10/14
  `-var mcp_*` gotcha re-applied, images pulled via the **v2 REST API** —
  v1 describe shows no image): **2 add, 3 computed refresh, 0 destroy**.
- Review: read-only subagent **Ready-to-proceed** (6 minors; 2 fixed
  in-session — dirty-check untracked files, id_tokens unit tests; rest
  inherited/cosmetic).
- Verification: webui **pytest 22 (+4) + vitest 89 (+2)**.

Cloud part (owner-approved):
- `terraform apply` — sa-webui created. `bash deploy/cloud-run/webui/deploy.sh`
  — image `20260913-2026-2f6a36f`, service
  `https://webui-$P-sa.run.app` placeholder form, invoker binding added.
- First `/api` call 403 → **IAM propagation delay** (~1 min); then
  `GET /api/v1/stories` from the public URL returned live data — full chain
  public webui → ID-token proxy → orchestration → MCP story → Cloud SQL OK.
- Domain: `mmz.sh` verified in Google Search Console (TXT via Cloudflare,
  owner-run — verification and the routing CNAME are **two separate DNS
  steps**); `gcloud beta run domain-mappings create` for
  `story-review.mmz.sh` (beta component install needed); CNAME
  `story-review → ghs.googlehosted.com` (owner had a typo
  `googlehoted`, caught via DoH — NXDOMAIN = record missing, wrong data =
  check contents); cert challenge retried only on Google's schedule
  (~15–60 min poll; HTTP 302→Google frontend proves routing before TLS).
  `https://story-review.mmz.sh` live: `/health` ok, stories load (first
  load slow = min-instances 0 cold start).
- Dev-server gotchas: docker push 401 until `gcloud auth configure-docker
  $REGION-docker.pkg.dev`; deploy.sh gcloud wrapper must pass
  `--project/--region` **per subcommand** (not global, not on the group).

Walkthrough (OPEN):
- story-02 session created and active (owner browser, turn 1/10).
- **Defect found on story-01**: facilitator opening-turn output failed
  strict-schema validation after corrective re-prompts → 422
  `VALIDATION_ERROR` after ~50 s (`flows._agent_failure` maps it 422).
  Consequences: (a) api-contract's `POST /sessions` error table
  (404/409/503) does not define a late 422 — doc/impl gap; (b) the session
  row persists **active with no turns** → empty chat, story blocked (409)
  until abandoned (D22 recover). Transient model behavior (story-02 and
  the inc-4 gate stories passed), but the failure path needs a fix:
  park/rollback the session on flow-1 agent failure + api-contract
  alignment. **Owner decision: fix at the start of the next session.**
- Two-user cookie-scoping proof not yet done (second browser).

### Increment 5 walkthrough — flow-1 422 defect FIXED (2026-09-14, dev
server; autonomous session, no cloud actions, Cloud SQL left RUNNING then
paused at wrap-up)

Owner decision (previous session): park/rollback the session on the flow-1
terminal-agent-failure path + align the api-contract error table. Done
locally, test-first:

- **Behavior**: in `flows.run_create_session`, a non-retryable `ApiError`
  raised after the session row exists now parks the session (the
  `records_store.update_session` chokepoint retires the story run in the
  same transaction — story released for a fresh key) and drops the
  idempotency claim, atomically (`_park_failed_session`; `idempotency.release`
  gained a `conn` param). Retryable failures keep the previous takeover
  semantics (session active, claim in_progress). A same-key retry of a
terminally-failed attempt (including the crash window: stale in_progress
  claim + parked session) is rejected `409 IDEMPOTENCY_KEY_REUSED`, with
  the fresh/stale claim row released — no agent re-invocation.
- **Docs**: `docs/design/api-contract.md` `POST /sessions` error paragraph
  now defines the late `422` (terminal agent failure → session parked,
  story released, retry with a new key) and the 409 same-key-retry nuance.
- **Review**: read-only subagent — 1 Important (guard path leaked a fresh
  in_progress claim row) + minors; Important fixed (release in the guard),
  park made best-effort (a park failure must not mask the client-visible
  terminal error; stuck session stays D22-recoverable), crash-window test
  added, style nit fixed.
- **Verification**: `make orchestration-test` **195 passed + 12 skipped**
  (baseline 191+12s; +4 tests: park+release with new-key recovery, same-key
  retry 409, retryable-keeps-active, stale-claim crash window).
- **NOT deployed**: ~~the CR `orchestration` service still runs the old code~~
  **DEPLOYED 2026-09-14** (dev server, owner approval in chat): Cloud SQL
  resumed first (`db-resume`, ~10 min STOPPED→MAINTENANCE→RUNNABLE), then
  `deploy/cloud-run/orchestration/deploy.sh`. First attempt FAILED the
  startup probe — Cloud SQL connector ephemeral-cert fetch cancelled →
  `TimeoutError` at pool init (instance freshly resumed; transient cold-
  start race, same image shape as the inc-4 PASS). Retry succeeded (image
  tag `20260914-…-91d563a`, carries fix `6ad0c2c`; note: that hash is
  stale after the D26 filter-repo — the log is authoritative).
  `/health` first read `degraded` (artifact/report unreachable — MCP
  services scale to zero, cold on first probe; direct `/health` on each
  returned 200), then fully **ok** (story/artifact/report/database all
  reachable).
- **Gotchas**: after `db-resume`, wait for RUNNABLE before deploying
  (connector timeout otherwise); health-probe failures on scale-to-zero
  MCP services are expected on the first probe after idle.
- **Gotcha (dev server)**: gcloud has **no default project configured** —
  `make db-pause`/`db-status` fail with "required property [project]";
  prefix with `CLOUDSDK_CORE_PROJECT=$PROJECT_ID` (after `source
  infra/envs/home.env`) or run `gcloud config set project` once. Cloud SQL
  paused at wrap-up (STOPPED/NEVER verified via `make db-status`).

## Increment 6 — observability, slices A+B (2026-09-15, PART — C and trace gate OPEN)

Owner decisions this session: flow-1-fix **live re-test deferred** (was
tested locally yesterday; re-test folds into the increment-6 live work);
**75% context compaction deferred** (telemetry-only for now — see
below); slice C (Cloud Monitoring terraform) next session.

### Slice A — structured JSON logging (orchestration + webui)

- New `orchestration/orchestration/structured_logging.py` and
  `webui/webui/structured_logging.py` (behaviorally identical copies —
  the units deploy as independent images; duplication deliberate over a
  new shared package): `JsonFormatter` (message/severity/service +
  extra correlation fields; non-JSON values stringed via `default=str`)
  + idempotent `configure_logging` (single stdout handler on the
  `storyreview` logger; Cloud Run stdout → Cloud Logging structured
  entries).
- Request-logging middleware in both app factories: one event per
  request with `method, path, status, duration_ms, correlation_id`;
  orchestration adds `user_id` (the `x-user-id` header when present);
  webui logs `/api` + `/health` only (static shell unlogged — public
  endpoint) and takes the correlation id from the response header.
- Orchestration ordering gotcha: the request-logging middleware is
  registered **before** the correlation middleware — Starlette runs the
  last-registered outermost, so correlation sets
  `request.state.correlation_id` before the log middleware reads it.

### Slice B — Item D facilitator telemetry callbacks

- New `shared/agent_kit/agent_kit/telemetry.py`: `context_level`
  policy (warn ≥ 50%, summarize ≥ 75% of the context limit) +
  `TelemetryCallbacks` — paired before/after **tool** events (tool
  name, status ok/error, duration; never args/results — content-safe)
  and before/after **model** events (latency, prompt/total tokens,
  context level/fraction; partial streaming responses skipped).
  Callback signatures verified against pinned **google-adk 2.8.0**
  (`Context`/`BaseTool`/`LlmRequest`/`LlmResponse` per Item D's
  "do not invent signatures" note).
- Wiring: `build_facilitator_runner` attaches
  `before_tool_callback=[lineage_guard, telemetry.before_tool]` — the
  guard must run first (a rejected call short-circuits before telemetry
  emits a start event with no matching end) — plus after-tool and
  before/after-model callbacks; `agents/facilitator/agent.py`
  `build_agent` extended with the three callback params (backward
  compatible; AE path unaffected). `context_token_limit` is a runner
  param (default None → no context classification) — deliberately NOT
  a config.yaml key to avoid four-agent config churn for one consumer.
- `agent_kit.structured_logging` (third identical copy, rationale as
  slice A) + `configure_logging(slug)` inside `create_facilitator_app`
  so the facilitator adapter's events actually reach Cloud Logging.
- **Deferred (owner)**: the 75% compaction action (typed summary
  validated before older ADK-session history replacement). Callbacks
  record `context_level=summarize`; compaction is an open mechanism
  decision (DatabaseSessionService event replacement). Recorded as the
  Item D remainder, not a deviation.

### Webui drive-by (owner request)

- GitHub link on the site header: `webui/static/index.html`
  (`source repo` → https://github.com/MMZ993/story-review, target
  `_blank` + `noopener`) + `.repo-link` styles in `app.css`. Baked into
  the image — goes live on the next webui deploy.

### Verification (2026-09-15, dev server, no cloud actions)

- orchestration **198 passed / 9 skipped** (full deterministic tier via
  a session-local throwaway Postgres; baseline had moved with the
  flow-1 fix, all green; +3 structured-logging tests)
- webui **pytest 25** (+3) + **vitest 89** (header link is static
  markup — no frontend test warranted)
- agent-kit **133** (+8), all four agent suites 3/3…4/4 green,
  `git diff --check` clean
- Nothing deployed: slices A/B ship in the next webui/orchestration
  image builds (slice-C session folds them in).

### Next (slice C, next session)

- Terraform: log-based metrics over the new structured events, Cloud
  Monitoring dashboard (per-agent latency/error/token, retry and
  validation exhaustion, idempotency, lock waits), the two designed
  alert policies (retry exhaustion, delegation-validation failure) —
  apply owner-approved per infra rules.
- Then the live trace gate + requirements-coverage callback row.
- Deploy the A+B images so the events start flowing before C reads
  them.

### Slice C — application events + Cloud Monitoring (2026-09-16, dev server; apply owner-approved in chat)

Retitle note: slices A+B remain local-only (images NOT rebuilt yet) —
slice C landed the *monitoring* side plus the orchestration application
events the alerts filter on. The trace gate and image deploys stay open.

**Code (test-first)**:

- New `orchestration/orchestration/app_events.py`: `log_app_event` on
  the `storyreview.app` logger (child of the JSON-configured root) +
  `alert_event_for` classification (`DELEGATION_VALIDATION` →
  `delegation_validation_failed`; retryable `UPSTREAM_UNAVAILABLE` /
  `AGENT_CALL_FAILED` / `RENDER_FAILED` → `retry_exhausted`).
- Wiring: the ApiError exception handler emits the alertable events for
  every route (correlation_id + user_id + agent + error_code,
  `error_message` — NOT `message`, see gotcha); `gate_decision` after
  `evaluate_gate`; `session_parked` after the atomic park transitions in
  turns_flow (`_persist_and_respond`), abandon, AND flow-1 terminal-
  failure `_park_failed_session` (review minor; `facilitator_turn=1`).
  Drive-by: `_upstream` gained an optional `agent` so the exhaustion
  event names the failing agent.
- Tests: `test_app_events.py` (4 — park emits gate+park events,
  continue emits gate only, 422 validation event, 503 exhaustion event;
  CaptureHandler fixture because the `storyreview` logger does not
  propagate, caplog cannot see it) + the park-event assertion folded
  into the flow-1 terminal-failure test.
- Review: read-only subagent **Ready-to-proceed**; its one actionable
  minor (missing flow-1 park event) fixed in-session, others were
  documentation nits.

**Terraform** (`infra/modules/monitoring`, wired in main.tf; logging +
monitoring APIs added to `required_services`):

- 4 log-based delta counters: `app-retry-exhausted`,
  `app-delegation-validation-failed`, `app-sessions-parked`,
  `app-gate-decisions` (label `outcome` via EXTRACT) — filters on
  `resource.type="cloud_run_revision" AND jsonPayload.service="orchestration" AND jsonPayload.event=...`.
- 2 alert policies (any single occurrence → incident, 300s ALIGN_SUM,
  auto-close 1h; **no notification channels — owner decision 2026-09-16**).
- 1 dashboard `story-review`: requests/s by service, orchestration p95
  latency, orchestration 5xx rate, application-events panel (classic
  timeSeriesFilter aggregations, XyChart tiles 2x2).
- Applied via `tmp/run-slice-c-plan.sh` + `tmp/run-slice-c-apply.sh`
  (targeted: module.monitoring + the two new API services). Evidence:
  dashboard `<dashboard-id>` under `$PROJECT_ID`, alert policies
  `6676422611572631903` / `719859346050099619`, 4 logging metrics + both
  APIs in state; MCP services re-verified healthy post-apply
  (`{"status":"ok"}` ×3 with impersonated sa-orchestration tokens).

**Gotchas learned (append-worthy)**:

- `make terraform-plan` without the deployed `-var mcp_*_image/_service_url`
  pointers plans the three MCP services for **deletion** (same family as
  runbook 06 spike gotcha). The tmp plan script reads the pointers from
  state — keep using it until the pointers move into home.tfvars.
- **`terraform apply -target=... <saved-plan>` does NOT exclude resources
  already inside the plan file**: the apply "modified" the three MCP
  services (the benign scaling-block normalization from runbook 06).
  Harmless — same image, services healthy after — but a new revision per
  service was created.
- Logging API: `google_logging_metric` counters need
  `metric_descriptor { metric_kind/value_type }` (no top-level
  metric_kind; no `counter {}` block in provider 6.50) + `label_extractors`
  with `EXTRACT(jsonPayload.<field>)`.
- Dashboards API via `dashboard_json`: **rejects `promqlQuery`** ("Unknown
  name promqlQuery") — use classic `timeSeriesFilter` + aggregation;
  **XyChart tiles must be ≥2x2**; alert policies on metric thresholds
  **may not set `notification_rate_limit`** (log-based policies only) —
  all three hit live at the apply, fixed in-module and recorded in its
  comments.
- Logging `extra` may not use `message` (LogRecord reserved attribute) —
  `KeyError: Attempt to overwrite 'message' in LogRecord`; use
  `error_message`.
- Impersonated ID tokens need `--include-email` (runbook 10 recipe);
  orchestration itself 403s for this identity (invoker is sa-webui —
  expected).

**Verification**: orchestration **202 passed / 12 skipped** (baseline
198+9s→198+12s pre-slice; +4 new); `terraform fmt` + `validate` clean;
`git diff --check` clean; nothing else deployed.

**Remaining for increment 6 close**: deploy orchestration (+webui) images
with slices A+B+C, live trace gate (paired tool events, model latency/
tokens, validation event, gate event, both alert metrics observed), then
requirements-coverage rows.

### Slice C deploy — orchestration + webui images (2026-09-16, dev server; owner-approved "lets deploy changes")

- Commits first (deploy scripts require a clean tree; tag↔commit map):
  `ae5d723` feat (app events + monitoring module), `d579e02` chore
  (runbook/HANDOFF). Gotcha: the **webui** dirty check also counts
  untracked files — the slice-C `tmp/` helper scripts blocked it; moved
  to `trash/run-slice-c-*.sh`.
- `deploy/cloud-run/orchestration/deploy.sh`: image
  `<orch-image-tag>` (commit `d579e02`), revision
  `orchestration-00022-kth`. `deploy/cloud-run/webui/deploy.sh`: image
  `<webui-image-tag>`, custom domain live.
- **Live verification** (public domain, read-only):
  `https://story-review.mmz.sh/health` → `{"status":"ok"}`;
  `/api/v1/stories` → **200** (proxy → orchestration → Cloud SQL +
  story MCP all reachable); **header `source repo` link live** (the
  increment-6 drive-by).
- **Structured logs live**: Cloud Logging read on
  `resource.type="cloud_run_revision" AND jsonPayload.service=...`
  returns the slice-A JSON request events for BOTH services (probe
  requests visible with path/status). The slice-C log-based metrics now
  have a source; the alert/trace gate (paired tool events, validation
  event, gate event, alert-metric observation) remains OPEN.
- Machine clock note: image tags printed `20260914-*` — the dev
  server's clock drifts; the commit hash in the tag is authoritative.

## Increment 6 close — live gate + three live root causes fixed (2026-09-16, dev server; cloud actions owner-approved in chat "yes please redeploy" / "please proceed with a fix" / "please commit")

Owner-driven live gates (browser, public domain). Four sessions this
session-window: `sess-cc2c9142` (2 turns), `sess-0a493ae9` (abandon),
`sess-28ee6721` (delegated turn + accept attempts), `sess-411c6c9b`
(accept → 500 pre-fix), `sess-7ed6d830` story-07 (full arc → reports).

### Gate evidence (increment 6 close)

- **Structured request logs** both services (probe requests with
  method/path/status/duration/correlation_id) — slice A live.
- **App events**: 5× `gate_decision` (all `continue`), 1×
  `session_parked` (abandon), fields incl. facilitator_turn.
- **Metric pipeline**: `app-gate-decisions` counted 2/2,
  `app-sessions-parked` 1/1 vs the logs; alert metrics
  `app-retry-exhausted`/`app-delegation-validation-failed` exist,
  policies enabled, 0 points (healthy run — no occurrences; pipeline
  proven by the sibling metrics). No `delegation_validation_failed` /
  `retry_exhausted` events occurred (design keeps them failure-only).
- **Slice B telemetry live from Agent Engine**: `model_call` start/end
  events as structured JSON on
  `resource.type=aiplatform…/ReasoningEngine` (model, duration_ms,
  prompt/total tokens, context level) — observed on story-07 turns.
  **`tool_call` events: none** — the facilitator made no tool calls in
  AE; open item: the AE-side MCP toolset creation may still hit the
  known metadata `default`-account signBlob failure (traceback seen on
  engine `1fb416d`); tool telemetry unobserved until that is resolved.
- **503-same-key retry live**: 5× fast-fail 503 on turns (scale-to-zero
  MCP cold start), webui retried same key every ~4–5 s → 200.

### Root causes found live and fixed (test-first)

1. **Stale MCP images (report 422/VALIDATION_ERROR at finalize)**:
   mcp-artifact/report/story Cloud Run images predated D19
   (`FinalizedReview.issues`), so the finalized-review save failed the
   union validation. Fixed by rebuilding all three (`63f39f6`) +
   terraform apply. **Gotchas**: plan without ALL six `-var` pointers
   (3 images + 3 service URLs) would DESTROY an MCP service; the
   report smoke fixture also predated D19 (added catalog entry,
   `17f73cd`).
2. **AE facilitator telemetry not wired**: slice B wired callbacks only
   in the local `build_facilitator_runner`; `ae_runtime
   build_facilitator_root_agent` built the agent without them. Fixed
   (`63f39f6`): telemetry bundle + `configure_logging` in the AE root
   agent (agent-kit 134). Engine redeployed as `facilitator-1fb416d`
   (smoke PASS) then `facilitator-17f73cd` (smoke PASS; both retained
   for the D5 prune). Orchestration repointed + redeployed
   (`orchestration-00023-q59`, then `-00024-4ld`).
3. **Live signed URLs could never work (500 at accept)**: docs assumed
   ambient Cloud Run ADC signs V4 URLs — wrong, token-only compute
   credentials have no private key (`ensure_signed_credentials`
   AttributeError). Fixed (`77e038b`): keyless IAM `signBlob` Signing
   credential (`orchestration/iam_signing.py`) as sa-orchestration
   (TokenCreator on itself, already in terraform); `warm_up` signs once
   at startup (fail-loud). Live root causes on the way: IAM rejects
   urlsafe-unpadded base64 (400); the deploy script's explicit env list
   didn't forward `ORCH_SIGNER_EMAIL` so the principal resolved to
   metadata `default` (400) — both fixed; startup probe (real signBlob)
   PASS on revision `orchestration-00028-n9p`. Orchestration 206+12s.
4. **Report encoding**: MD objects served as bare `text/markdown`
   (browsers guess cp1252 → mojibake) and PDF em dash → `?`. Fixed
   (`2bf6122`): GCS upload content type `text/markdown; charset=utf-8`
   (wire literal unchanged), `_latin1` transliterates `—` → ` - `.
   mcp-report 38 (+2); redeployed, smoke PASS. Existing report objects
   keep the old metadata (regenerate to fix).

End-to-end proof: story-07 accepted → finalized → reports downloaded
from the public domain.

### D27 open item closed — AE MCP toolsets + tool_call telemetry live (dev server; cloud actions owner-approved "run it")

Three stacked live root causes, each fixed test-first on `main`:

1. **ID-token mint via signBlob (the recorded D27 open item)**:
   `_IdTokenAuth._mint` built `compute_engine.IDTokenCredentials` with
   defaults — google-auth then mints via an **IAM Signer over
   `service_account_email`**, which AE compute credentials report as
   `"default"` → IAM 400 "Invalid form of account ID default" → ADK
   dropped the toolset ("agent will run without the tools"). Fix
   (`f6b8024`): `use_metadata_identity_endpoint=True` — the metadata
   identity endpoint mints the audience token directly, no signing, no
   account resolution.
2. **after_tool callback signature**: first smoke then failed with
   `TypeError: after_tool() missing 1 required positional argument:
   'result'` — ADK calls canonical after-tool callbacks with keyword
   `tool_response=`, never positional `result` (only observable once a
   tool call actually happened; local tests called it positionally).
   Fix (`1b933d1`): accept both, `tool_response=` pinned by a new test.
3. **Toolset connect timeout**: smoke PASS but one toolset still
   dropped out — "timed out after 10.0s waiting for the session to
   become ready" (MCP Cloud Run scale-to-zero cold start; the artifact
   toolset took ~10 s itself, live logs show it connected just in
   time). Fix (`573011d`): AE toolset connect timeout 10 s → 30 s.

- Engines: `facilitator-f6b8024` (1782976851694583808, FAIL — cause 2),
  `facilitator-1b933d1` (1090266934009659392, smoke PASS but cause 3),
  `facilitator-573011d` (**7147608432822976512, current**, smoke PASS,
  both toolsets load, no dropouts) — all retained for the D5 prune.
- Orchestration repointed (resource **and** version — resource is what
  `ae_client` dials, version is only the audit label) + redeployed as
  `orchestration-00030-lfz`; `/health` ok (first probe read `degraded`
  on the report MCP cold start — expected, second probe ok).
- **Live gate PASS**: story-07 session over the public domain, PO turn
  asking about story content → paired `tool_call` start/end events for
  `get_story` (status ok) + `model_call` events with tokens/duration on
  the engine's structured logs; test session abandoned afterwards
  (parked). D27 amendment 2 records the deviation.
- Verification: agent-kit **136** (+2), agents 4×3-4. Machine clock
  drift note: real UTC lags the session labels — logs were queried with
  explicit windows, not "since 2026-09-16".
