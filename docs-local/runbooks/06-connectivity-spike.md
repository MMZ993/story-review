# Runbook 06 — Phase 1 connectivity spike

Executes `docs-local/plans/phase-1-connectivity-spike.md`. Disposable
resources only; teardown is mandatory after evidence.

Status: IN PROGRESS — increments 1–3 done (increment 3 deployed and verified
2026-09-05); increments 4–5 (Agent Engine caller, decision gate/teardown)
remain.

## Increment 1 — Confirm interfaces and write tests (DONE 2026-09-05, local only)

### Interface confirmation (read-only; nothing executed against GCP)

Confirmed locally with `uv run --with ...`:

| Component | Version | Evidence |
|---|---|---|
| google-adk | 2.8.0 | `uv run --with google-adk python -c "import google.adk; print(google.adk.__version__)"` |
| mcp (Python SDK) | 2.1.1 | package metadata; note: 2.x renamed `FastMCP` → `MCPServer` (`mcp.server.mcpserver`) |
| google-cloud-aiplatform | 2.1.0 | `uv run --with "google-cloud-aiplatform[adk]"`; not pulled in by google-adk itself — declared explicitly in `spike_agent/requirements.in` and locked |

Agent Engine runtime-SA support (the blocking question):

- `adk deploy agent_engine AGENT --project=... --region=...` exists in ADK 2.8.0.
- The runtime service account is set via `.agent_engine_config.json` in the
  agent folder; the ADK CLI passes that config dict to
  `vertexai.agent_engines.create/update`, whose signature explicitly accepts
  `service_account: Optional[str]` (verified in
  `vertexai/agent_engines/_agent_engines.py`, google-cloud-aiplatform 2.1.0).
- Deployment form planned for increment 4:

  ```bash
  source infra/envs/home.env
  adk deploy agent_engine \
    --project="$PROJECT_ID" --region=europe-west4 \
    --agent_engine_id=<disposable-id> \
    spikes/connectivity/spike_agent
  ```

  with `.agent_engine_config.json` carrying `service_account` (the
  `sa-facilitator` email) and `env_vars` (Cloud Run service URL/audience).

MCP service interface: `MCPServer` (mcp 2.1.1) with two tools
(`persist_session`, `restore_session`), flat keyword arguments, structured
JSON results, streamable-HTTP app for Cloud Run (later increment).

### Deviation from the plan layout (recorded, minor)

The plan names the service package `mcp/` and the agent package `agent/`; a
local top-level package named `mcp` shadows the `mcp` SDK import
(`from mcp.server.mcpserver import ...`). Packages are therefore
`spikes/connectivity/spike_mcp/` and `spikes/connectivity/spike_agent/`.
No other deviation.

### Tests: failing → passing

Files: `spikes/connectivity/tests/` (`test_store.py`, `test_contract.py`,
`test_agent_probe.py`). First run failed for the expected reason
(`ModuleNotFoundError: no module named 'agent'`/`spike_*` — no
implementation yet), then passed after implementing:

- `spike_mcp/store.py` — validated persist/restore requests, persist-once
  semantics (`AlreadyStoredError` on a different marker, idempotent re-persist),
  defined not-found result carrying the request correlation ID.
- `spike_mcp/server.py` — `MCPServer` with exactly the two tools; every call
  requires a resolved `Principal` via a provider hook (tests inject a fake
  verified principal; the deployed service verifies a Google ID token —
  increment 3); correlation ID logged per call.
- `spike_mcp/principal.py` — verified-caller identity type.
- `spike_agent/session_probe.py` — caller-generated correlation ID, forwarded
  with every MCP request through an injected transport; tool payloads
  returned without interpretation.

Command (declared in the Makefile; test stack pinned via
`spikes/connectivity/tests/requirements.lock`):

```bash
make spike-connectivity-test
```

Result: **14 passed** (2026-09-05, offline; in-memory store, in-memory MCP
transport, fake transport in the probe). All tests are deterministic — the
correlation-ID test asserts UUID shape rather than uniqueness of random draws.

Locked requirements compiled with `uv pip compile`:
`spike_mcp/requirements.lock`, `spike_agent/requirements.lock`,
`tests/requirements.lock`.

Gotchas learned (SDK 2.x):

- `mcp` 2.x renamed `FastMCP` → `MCPServer`; `CallToolResult` uses
  `is_error` / `structured_content` (snake_case model fields).
- Tool arguments arrive as flat keyword params; a nested input model is not
  populated from a flat client `arguments` dict.
- Tool-handler exceptions are wrapped by the server into a generic error
  result — error detail does not reach the client; the auth contract is
  therefore asserted via `is_error` plus "no store mutation occurred".

### Independent review

A read-only review flagged: `google-cloud-aiplatform` missing from the agent
lock (fixed: declared explicitly), the Make target resolving unpinned test
deps (fixed: `tests/requirements.lock` via `--with-requirements`), and one
probabilistic uniqueness test (fixed: assert UUID shape). All addressed same
session; auth-boundary scope confirmed correct for increment 1 (real ID-token
verification arrives with increment 3, before any HTTP deployment).

## Increment 2 — Database migration and IAM db access (PROPOSED — awaiting owner review)

### Discovery (read-only, 2026-09-05)

- `gcloud sql instances describe` shows `databaseFlags` **empty**: the
  `cloudsql_iam_authentication` instance flag is missing — IAM database
  login would fail. Runbook 04 gap; fixed by the Terraform patch below.
- `gcloud sql users list`: only the built-in `postgres` user; no IAM
  database users exist yet.
- `sa-artifact-mcp` already holds project-level `roles/cloudsql.instanceUser`
  (Runbook 04) — necessary but not sufficient: an IAM database user entry and
  a schema it owns are also required (PostgreSQL 16 IAM users start with
  CONNECT only; CREATE on `public` is revoked by default).

### 2.1 Terraform patch — enable IAM db auth + create IAM database users (EXECUTED 2026-09-05)

Patch applied to `infra/modules/cloud-sql/main.tf`: added
`database_flags { cloudsql.iam_authentication = "on" }` (PostgreSQL flag
name uses a dot; the first attempt `cloudsql_iam_authentication` failed with
`Error 404 invalidFlagName` — gotcha recorded in infra-rules) and
`google_sql_user.iam_runtime_users` (`type = "CLOUD_IAM_SERVICE_ACCOUNT"`, no
passwords, one per `iam_login_sa_emails`).

Validation (agent-run, read-only):

```bash
cd infra
terraform fmt -check -recursive   # PASS
terraform validate                 # PASS
```

Plan (saved as `infra/home-iam-db-auth.tfplan`, reviewed by owner before apply):

```bash
cd infra && source ../infra/envs/home.env  # if shell vars needed
terraform plan -var-file=envs/home.tfvars -out=home-iam-db-auth.tfplan
```

Plan summary: **4 to add** (IAM db users for orchestration, facilitator,
artifact-mcp, report-mcp), **1 to change** (`google_sql_database_instance.sessions`
+ `database_flags cloudsql.iam_authentication="on"`), **0 to destroy**.
First apply attempt failed on the misspelled flag (404 invalidFlagName);
re-planned with the correct name and applied.

Impact reminder: the flag change **restarts the instance** (db-f1-micro,
~1–2 min, no data). In practice the update completed in 21s.

Apply history (both gotchas recorded in infra-rules):

1. First apply failed: flag name `cloudsql_iam_authentication` → Error 404
   invalidFlagName. Fixed to `cloudsql.iam_authentication`; second apply
   **set the flag successfully** (instance updated, 21s).
2. Same apply then failed on the IAM users: SA usernames must be created
   **without the `.gserviceaccount.com` suffix** (`sa-x@project.iam`,
   Error 400 otherwise). Fixed via `trimsuffix`; re-planned as
   `home-iam-db-users.tfplan`: **4 to add, 0 to change, 0 to destroy**.

Apply (owner-run, tier-2):

```bash
cd infra
terraform apply home-iam-db-users.tfplan   # retry after the suffix fix
```

Post-apply verification (read-only):

```bash
source infra/envs/home.env
gcloud sql instances describe "$PROJECT_ID-sessions" \
  --format='value(settings.databaseFlags)'
# expect: [{cloudsql_iam_authentication  on}]
gcloud sql users list --instance="$PROJECT_ID-sessions" \
  --format='table(name,type)'
# expect: postgres BUILT_IN + 4 CLOUD_IAM_SERVICE_ACCOUNT entries
```

### 2.2 One-time admin bootstrap (`sql/000_bootstrap.sql`) — EXECUTED 2026-09-05

PostgreSQL has no passwordless first-admin path for granting IAM users
  privileges: the only bootstrap is a `postgres` password session. No local
  proxy or psql is installed; the admin session runs through the Cloud SQL
  Python Connector (`sql/admin_apply.py`, deps locked in
  `sql/requirements.lock`), which connects via the Cloud SQL Admin API with an
  ephemeral certificate. It applies 000 (schema), 001 (migration), and 002
  (least-privilege grants) in one transaction, substituting `__ROLE__` with
  the quoted `"sa-artifact-mcp@$PROJECT_ID.iam"` identifier.

Owner procedure (tier-2; password set owner-run so the secret never transits
  the agent):

1. `gcloud sql users set-password postgres --instance="$PROJECT_ID-sessions" --prompt-for-password`
2. Store the value as `SPIKE_DB_PASSWORD` in gitignored
   `infra/envs/home.env` (verified ignored, never committed) per D7;
3. Run `source infra/envs/home.env && make spike-db-bootstrap`.

Rotation stance per amended D7: keep in `home.env` for the home phase (rare
  use — only schema/grant bootstraps; in-schema migrations run IAM-auth,
  passwordless); rotate when the phase ends.

Execution evidence (2026-09-05): owner set the password and placed it in
  gitignored `infra/envs/home.env` (verified ignored, never committed; kept
  there per amended D7); agent ran `make spike-db-bootstrap` with the owner's
  approval. Final output:

```text
applying 000_bootstrap.sql
applying 001_session_marker.sql
applying 002_grants.sql
bootstrap complete: schema, table, and grants applied
```

Gotchas learned during execution (also in infra-rules):

- outbound TCP **5432 is blocked** on this network; the connector must dial
  Cloud SQL's dedicated **port 3307** (`SPIKE_DB_PORT` override in
  `admin_apply.py`); one intermittent connection timeout — retry succeeded;
- the IAM role name contains `-`/`@` → must be emitted as a **quoted** PG
  identifier;
- Cloud SQL's `postgres` admin **cannot SET ROLE to IAM roles**, so
  `CREATE SCHEMA ... AUTHORIZATION <iam-role>` fails
  (`InsufficientPrivilege`); the schema is owned by `postgres` and the IAM
  role gets `USAGE, CREATE` + table grants instead (002_grants.sql) —
  functionally equivalent for the spike.

Deviation recorded as D7 in local-decisions (§2.4 below): password lives in
  the gitignored home env file, services stay passwordless.

### 2.3 Migration application and verification

The admin session applies all three SQL files (schema ownership, migration,
  grants) — no impersonation or run-migration.sh needed for the spike. The
  production-shaped `run-migrations.sh` (deployment SA, ordered files) is
  built in a later phase.

Verification of the migration result must go through the same connector path
  the service uses (increment 3 end-to-end); the admin session only applies it.

### 2.4 D7 — admin password in the gitignored env file (local-decisions entry)

Runtime connectivity stays passwordless (IAM database authentication, no
  stored secrets in services). The frozen design's own migration path needs a
  `postgres` admin session for schema/grant bootstraps; in the home phase
  (no pipelines, no vault) that password lives only in gitignored
  `infra/envs/home.env`, is used rarely, and is rotated at phase end. Full
  wording in local-decisions.md D7.

### Decisions taken (2026-09-05, superseding the earlier open questions)

1. Terraform patch approved and applied in two steps (flag; then IAM users
   after the suffix fix) — §2.1.
2. Admin-password bootstrap approved and executed via the Cloud SQL Python
   Connector — §2.2.
3. D7 amended: password kept in gitignored `home.env` (not rotated per use);
   rotation procedure in §2.5. No tokenCreator/impersonation grant needed.

### 2.5 Admin password rotation procedure (owner-run, per D7)

Rotate when the home phase ends, or whenever the machine is shared.
  Interactive on purpose — the new secret transits only the owner's prompt
  and `home.env`, never a script or the agent.

```bash
source infra/envs/home.env
# 1. generate a fresh value (suggestion): openssl rand -base64 24
gcloud sql users set-password postgres \
  --instance="$PROJECT_ID-sessions" --prompt-for-password
# 2. update SPIKE_DB_PASSWORD in infra/envs/home.env with the same value
# 3. optional idempotent check (safe to re-run; IF NOT EXISTS + grants):
#    make spike-db-bootstrap   -> expect "bootstrap complete"
```

No make target for this by design: interactive secret entry does not belong
  in scripted targets.

## Increment 3 — Build and provision the Cloud Run MCP service (TODO)

## Increment 3 — Build and provision the Cloud Run MCP service (DONE 2026-09-05 — deployed + verified)

### What was implemented (all local; no GCP writes yet)

Service code in `spikes/connectivity/spike_mcp/`:

- `store_sql.py` — Cloud SQL-backed `SessionMarkerStore` over an asyncpg pool
  on the Cloud Run-injected unix socket `/cloudsql/<instance-connection-name>`;
  IAM db auth via a fresh runtime-SA OAuth token as the password (scope
  `sqlservice.login`); single-statement conditional upsert preserves
  persist-once semantics (`AlreadyStoredError` when the upsert returns no row);
  database `postgres` (where the increment-2 migration lives), table
  `spike.session_marker`.
- `auth_middleware.py` — pure-ASGI middleware (same task → contextvar visible
  to tool handlers): `Authorization: Bearer` verified against the configured
  audience (service URL) with `google.oauth2.id_token.verify_oauth2_token`;
  missing/invalid token → 401; unset audience → **503 fail-closed** (covers the
  window between first and second apply); `/healthz` exempt.
- `app.py` / `main.py` — wiring: stateless streamable-HTTP MCP app + `/healthz`
  + middleware; SQL store selected from env (`SPIKE_INSTANCE_CONNECTION_NAME`,
  `SPIKE_SA_EMAIL`), audience from `SPIKE_SERVICE_URL`; uvicorn entrypoint.
- `../Dockerfile` (python:3.13-slim, non-root, locked deps) and
  `../deploy-mcp.sh` (build → push to existing AR `service-images`, prints
  the image ref for the Terraform `-var`).

### Tests: failing → passing

New tests: `test_auth_middleware.py` (401/503/healthz/valid-token boundary
behavior with a fake verifier), `test_store_sql.py` (SQL store contract
against a fake asyncpg pool; parameterized statements asserted),
`test_app.py` (full authenticated persist/restore round trip over the real
streamable-HTTP transport via the ASGI test client). First run failed for the
expected reason (`No module named 'spike_mcp.store_sql'`).

```bash
make spike-connectivity-test   # 26 passed (was 14; +12 new)
```

Local container smoke (no GCP): `docker build` OK; `GET /healthz` → 200;
`POST /mcp` without a token → 401.

Gotchas learned (SDK):

- mcp 2.x streamable-HTTP enforces a Host-header check (DNS-rebind
  protection) → 421 for unexpected hosts; the app derives the expected host
  from `SPIKE_SERVICE_URL` (tests pass `http_host` explicitly).
- `stateless_http=True` returns no `Mcp-Session-Id`; clients must not expect one.
- `docker push` to Artifact Registry does not use ADC: without
  `gcloud auth configure-docker <region>-docker.pkg.dev` the push fails with
  "denied: Unauthenticated request" (recorded in infra-rules too).

Execution evidence (2026-09-05): image pushed by the owner as
  `spike-connectivity-mcp:20260905-1616-1bba7f7`
  (digest sha256:20ab2a6...61cb67) after configuring the docker credential
  helper for europe-west4-docker.pkg.dev.

### Terraform module `infra/modules/connectivity-spike` (validated, not applied)

`google_cloud_run_v2_service` (name `spike-connectivity-mcp`):
europe-west4, runs as `sa-artifact-mcp`, ingress
`INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` (internal + Cloud LB), deletion
protection off (disposable), min 0 / max 1 instances, request concurrency 4,
timeout 60s, 512Mi/1cpu, `/cloudsql` socket attached via the Cloud SQL output,
env per above. IAM: `roles/run.invoker` only for `sa-facilitator` (no public
member exists → anonymous denied by default) and project-level
`roles/cloudsql.client` for `sa-artifact-mcp` (instanceUser grants IAM login
but not `cloudsql.instances.connect`).

Root wiring is **count-gated** on `var.spike_mcp_image` (default `""`), so
routine plans/validates are unaffected until the spike deploy runs.

Provider schema notes (google 6.50): template-level fields are
`timeout` (duration string), `max_instance_request_concurrency`, `scaling`
block, `annotations` directly on `template` (no metadata/spec nesting).

Read-only checks executed (agent, tier 1):

```bash
cd infra
terraform fmt -check -recursive   # PASS (after fmt)
terraform validate                 # PASS
terraform plan -var-file=envs/home.tfvars -detailed-exitcode   # 0 = no drift, module disabled
terraform plan -var-file=envs/home.tfvars \
  -var 'spike_mcp_image=<dummy>'   # exactly: 3 to add (service, invoker IAM, cloudsql.client)
```

### Deployment procedure (PROPOSED — tier-2, owner approval per step)

Deliberate **two-step apply**: the ID-token audience is the service URL,
which is only known after the first apply; until the second apply the service
fails closed (503 on MCP traffic).

```bash
# 0. one-time per workstation: let docker push authenticate via gcloud
#    (writes a credHelpers entry to ~/.docker/config.json; no GCP change).
#    Without it the push fails: "denied: Unauthenticated request ... uploadArtifacts".
gcloud auth configure-docker europe-west4-docker.pkg.dev

# 1. build + push image (tier-2)
spikes/connectivity/deploy-mcp.sh        # prints IMAGE=<region-docker.pkg.dev/...>

# 2. first plan/apply: create service with empty audience (tier-2)
cd infra
terraform plan -var-file=envs/home.tfvars \
  -var 'spike_mcp_image=<IMAGE>' -out=home-spike-mcp-1.tfplan
terraform apply home-spike-mcp-1.tfplan

terraform output -raw connectivity_spike   # note service_url  (see output below)

# 3. second plan/apply: set the audience env (tier-2)
terraform plan -var-file=envs/home.tfvars \
  -var 'spike_mcp_image=<IMAGE>' -var 'spike_service_url=<SERVICE_URL>' \
  -out=home-spike-mcp-2.tfplan
terraform apply home-spike-mcp-2.tfplan
```

### Post-deploy verification (read-only, executed 2026-09-05)

Invoker IAM (gcloud, v1 surface):

```text
bindings:
- members: [serviceAccount:sa-facilitator@...]
  role: roles/run.invoker
```
No allUsers/allAuthenticatedUsers member — anonymous invocation denied.

Configuration via the Cloud Run **v2 API** (gotcha: `gcloud run services
describe` uses the v1 surface, which does not expose v2 fields like
`ingress`/`uri`/`volumes`; `curl run.googleapis.com/v2/...` with an access
token does):

```text
ingress          = INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCING  (internal + LB)
uri              = https://spike-connectivity-mcp-kxcnogex4q-ez.a.run.app
serviceAccount   = sa-artifact-mcp@...
volumes          = cloudsql -> [$PROJECT_ID:europe-west4:$PROJECT_ID-sessions]
volumeMounts     = /cloudsql
scaling          = maxInstanceCount 1 (min defaults to 0)
timeout/conc     = 60s / 4
env              = SPIKE_SERVICE_URL=<uri>, SPIKE_SA_EMAIL, SPIKE_INSTANCE_CONNECTION_NAME
latestReadyRevision = spike-connectivity-mcp-00002-b8l
```

`GET /healthz` from this workstation returns **404** — expected: the direct
external path is not reachable with internal-and-LB ingress, which is exactly
what increment 4 tests from Agent Engine (decision gate per the plan).

Execution history (tier-2, owner-approved): image pushed
`spike-connectivity-mcp:20260905-1616-1bba7f7`; apply 1 (3 added, 21s —
service created with empty audience, fail-closed 503); apply 2 (env audience
set, revision ...-00002). Mid-flight fix: the first apply had used the
v1-style `run.googleapis.com/cloudsql-instances` annotation; Cloud Run
normalized it into a `volumes.cloudSqlInstance` block, and the second plan
would have removed the volume (flip-flop). The module now declares the
v2-native `volumes` + `volumeMounts` (recorded as a gotcha in infra-rules).

## Increment 4 — Deploy and prove the Agent Engine caller (EXECUTED 2026-09-05 — PASS)

### What is implemented locally

`spike_agent/agent.py` exports the disposable `root_agent` (`gemini-2.5-flash`)
with exactly `persist_session` and `restore_session` ADK function tools.
`transport.py` obtains a Google ID token from the active runtime credentials
with `SPIKE_SERVICE_URL` as its audience, then opens a stateless MCP
streamable-HTTP client to `$SPIKE_SERVICE_URL/mcp`. `tools.py` forwards
caller-provided session IDs, markers, and correlation IDs without
interpretation. `mcp==2.1.1` is now pinned in the agent lock.

`deploy-agent.sh` stages the package and copies the lock as the Agent Engine
`requirements.txt`; it writes a staging-only `.agent_engine_config.json` with
`sa-facilitator` and the Terraform output service URL. The staging directory
is retained under `/tmp/spike-agent.*` for diagnosis and contains no secrets.

`run-agent-trace.sh` makes one persist and one restore Agent Engine `:streamQuery`
request (each auto-creating its own Agent Engine session; no session_id is
sent — see gotchas 3–4) with one generated database session ID, marker, and
correlation ID. It exits nonzero unless response events (snake_case
`function_response`) show `stored=true` then `found=true` with all three exact
values. It retains raw responses under `/tmp/spike-trace.*`; sanitize before
copying evidence.

### Deployment and trace procedure

Impact: `deploy-agent.sh` is tier 2 — it creates a disposable Agent Engine
resource and incurs on-demand Agent Engine/Vertex usage. `run-agent-trace.sh`
issues two requests and intentionally writes one disposable session-marker row.
No Terraform, IAM, or ingress change occurs in this increment.

```bash
# Read-only preflight: confirm the target Cloud Run URL and facilitator identity.
source infra/envs/home.env
terraform -chdir=infra output -json connectivity_spike | jq .
terraform -chdir=infra output -json service_accounts | jq '.runtime."sa-facilitator"'
terraform -chdir=infra plan -detailed-exitcode -lock=false -var-file=envs/home.tfvars \
  -var "spike_mcp_image=europe-west4-docker.pkg.dev/$PROJECT_ID/service-images/spike-connectivity-mcp:20260905-1616-1bba7f7" \
  -var 'spike_service_url=https://spike-connectivity-mcp-kxcnogex4q-ez.a.run.app'
# expect exit code 2 with exactly ONE benign in-place change: removal of an
# extra top-level `scaling` block (manual_instance_count=0/min=0) that the
# provider added to state but the module never declared (same normalization
# family as the increment-3 volumes flip-flop). Do NOT apply to "fix" it —
# it re-appears on refresh and only creates a needless revision. Module is
# torn down in increment 5. If anything ELSE appears in the plan, stop and
# investigate before deploying.
# Gotcha: the spike module is count-gated on var.spike_mcp_image (default "")
# and its env vars come from var.spike_service_url (default ""), so a plan
# without both -var flags reports destroy/update drift on the spike resources
# even when nothing changed. Always pass both deployed values (or move them
# into envs/home.tfvars if this bites again).

# Tier-2: deploy a new, versioned disposable Agent Engine resource.
spikes/connectivity/deploy-agent.sh
# Record the printed agent-engine ID, staging directory, timestamp, and CLI result.

# Request usage: run the two-request persist/restore proof.
spikes/connectivity/run-agent-trace.sh <printed-agent-engine-id>
# Expect: PASS: persisted and restored the exact session ID, marker, and correlation ID.
```

Before accepting the result, capture the Agent Engine resource's runtime
service account (deployment CLI result or Agent Engine describe output), the
Cloud Run v2 configuration/IAM evidence already captured in increment 3, and
sanitized `persist.json`/`restore.json` values. Query Cloud Logging by the
printed correlation ID across the Agent Engine and Cloud Run resources, for
example:

```bash
source infra/envs/home.env
CORRELATION_ID=<printed-correlation-id>
gcloud logging read "textPayload:$CORRELATION_ID OR jsonPayload.correlation_id=$CORRELATION_ID" \
  --project="$PROJECT_ID" --limit=100 --format=json > /tmp/spike-correlation-logs.json
```

Record the command timestamps, service URL/audience form, runtime identities,
correlation ID, sanitized tool responses, and whether internal ingress passed.
If Agent Engine cannot reach the internal-ingress service, do not retry with
configuration changes here: proceed to Increment 5's documented default-ingress
decision gate.

### Execution record (2026-09-05)

Final PASS run: agent engine `3787430529595342848` (numeric ID, see gotcha 1),
correlation ID `1fe5d7f691e84ff689a2c9ba73b49dbf`, session
`spike-1fe5d7f691e8`, marker `marker-4ff689a2c9ba`, trace dir
`/tmp/spike-trace.am2lf2` (raw, retained locally).

- persist response: `{stored: true, session_id: spike-1fe5d7f691e8,
  correlation_id: 1fe5d7f6…49dbf}`; restore response: `{found: true,
  session_id: …, marker: marker-4ff689a2c9ba, correlation_id: …}` — both
  asserted by the script's jq guards; script printed PASS.
- Deployed resource spec (GET reasoningEngines/3787430529595342848):
  `spec.serviceAccount = sa-facilitator@$PROJECT_ID.iam.gserviceaccount.com`,
  `spec.effectiveIdentity` the same, `deploymentSpec.env` =
  `SPIKE_SERVICE_URL=https://spike-connectivity-mcp-kxcnogex4q-ez.a.run.app`
  (evidence in `/tmp/spike-agent-engine-describe.json`).
- Cross-resource correlation evidence: Cloud Run stderr logs at 20:16:17
  (persist_session) and 20:16:20 (restore_session), both carrying
  `correlation_id=1fe5d7f6…` and `principal=sa-facilitator@…`.
- **Ingress gate result: internal ingress FAILED** — Agent Engine's calls were
  rejected at the edge (GFE 404, no Cloud Run request logs) under
  `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`. The approved fallback
  (`INGRESS_TRAFFIC_ALL` + mandatory ID-token audience auth + invoker-only
  IAM) was applied via reviewed plan `home-spike-ingress-fallback.tfplan` and
  the trace then passed. Recorded as **D8** in `docs-local/local-decisions.md`.
- Extra tier-2 applies during debugging: `home-spike-agent-iam.tfplan`
  (sa-facilitator → roles/aiplatform.user, gotcha 3) and two MCP image
  rollouts (final image `spike-connectivity-mcp:20260905-2204-d0e9a43`,
  gotchas 5–6).
- Superseded agent engines deleted by the owner (`…5685908878764539904`,
  `…7840881300461322240`, with `?force=true` because child sessions exist);
  `…3787430529595342848` remains live until increment 5 teardown.

### Gotchas learned live (all reproducible from this session)

1. `adk deploy agent_engine --agent_engine_id=<id>` in ADK 2.8.0 **skips
   create()** and `update()`s a nonexistent reasoningEngine → bare
   `400 INVALID_ARGUMENT`. Deploy without the flag; the platform mints a
   numeric ID; parse `Created a new instance: projects/…` from the output.
2. The same CLI **exits 0 after printing `Deploy failed`** — check the output,
   not the exit code (deploy-agent.sh does).
3. The runtime SA needs `aiplatform.sessions.create` (in
   `roles/aiplatform.user`) or every `stream_query` fails with a **silently
   empty stream**; the real 403 only shows in
   `aiplatform.googleapis.com%2Freasoning_engine_stderr`. Also expect 1–3 min
   IAM propagation before `aiplatform.endpoints.predict` works.
4. The Agent Engine **query API needs `:streamQuery?alt=sse`** for streaming
   class methods — `:query` with `classMethod: async_stream_query` returns
   `400 … 'async_generator' object is not iterable`. The response body is
   concatenated JSON documents (not SSE-framed), and ADK events serialize
   `function_response` in **snake_case** on the wire.
5. mcp 2.1.1 removed the `headers=` kwarg from `streamable_http_client` —
   pass a custom `httpx.AsyncClient(headers=…)` instead.
6. `google.auth.transport.requests` (used by `id_token.verify_oauth2_token`)
   requires the `requests` package at call time — it was missing from the MCP
   image; symptoms: middleware 401 "invalid token" with the ImportError only
   in `run.googleapis.com%2Fstderr`. Now pinned in spike_mcp requirements.
7. mcp 2.1.1 servers without an output schema return tool dicts as JSON
   **text content** (`structuredContent` is null) — the client must fall back
   to parsing `result.content[0].text` (spike_mcp `tool_payload` always did;
   spike_agent transport now mirrors it).
8. Structured Cloud Run log lines are hard-wrapped (~40 cols), so full
   correlation IDs are never contiguous — search Logging by a short unique
   prefix (`textPayload:"<first 12 chars>"`).


### Verification (local, 2026-09-05)

```bash
make spike-connectivity-test  # PASS: 29 passed (one upstream deprecation warning)
bash -n spikes/connectivity/deploy-agent.sh spikes/connectivity/run-agent-trace.sh
SPIKE_SERVICE_URL=https://spike.example PYTHONPATH=spikes/connectivity \
  uv run --with-requirements spikes/connectivity/spike_agent/requirements.lock \
  python -c 'from spike_agent.agent import root_agent; print(root_agent.name)'
# expect: connectivity_spike
```

Known first-run risks (record the outcome as gotchas): (a) the trace uses the
`:query` endpoint with `classMethod: async_stream_query`; the aiplatform SDK
itself uses `:streamQuery?alt=sse` for this method — if `:query` rejects it,
switch `ENDPOINT` to `.../${AGENT_ENGINE_ID}:streamQuery?alt=sse` (same body).
(b) the request `session_id` values are never pre-created via
`create_session`; if Agent Engine rejects an unknown session, omit
`session_id` (auto-create) and adjust the jq assertions accordingly.

No Agent Engine deployment or live trace has yet been executed in this entry.

## Increment 5 — Decision gate and cleanup (TODO)

### Decision gate — recorded

- **D8 confirmed** (`docs-local/local-decisions.md`): internal ingress
  (`INTERNAL_LOAD_BALANCER`) rejected Agent Engine egress at the edge (404,
  no request logs); fallback applied per the phase-1 plan — ingress changed to
  default (`INGRESS_TRAFFIC_ALL`) only, with mandatory ID-token audience auth
  + invoker-only IAM retained. End-to-end trace PASS on the fallback (increment 4
  evidence). Phase 1 exit criterion met (passing chain + owner-approved,
  documented fallback).
- Cost check (read-only, 2026-09-06): budget `trial-80pct` unchanged — limit
  1114 PLN/month, credits included, no 80% threshold notification received.
  Recurring post-teardown cost: only Cloud SQL `db-f1-micro` (~PLN 30–40/mo
  equivalent; pausable with `gcloud sql instances patch --activation-policy
  NEVER` when idle).

### Teardown inventory (verified live this session)

- Cloud Run service `spike-connectivity-mcp`
  (`https://spike-connectivity-mcp-kxcnogex4q-ez.a.run.app`, ingress ALL per D8).
- Terraform plan with `spike_mcp_image=""`: **0 to add, 0 to change, 4 to
  destroy** (Cloud Run service + `roles/run.invoker` on sa-facilitator,
  `roles/aiplatform.user` + `roles/cloudsql.client` on sa-artifact-mcp).
  Nothing else in the plan — verified.
- Agent Engine `3787430529595342848` (deployed via ADK SDK, not Terraform).
- AR images: 3 digests under `service-images` (untagged after Cloud Run
  deletion still counts negligible storage).
- DB marker rows: `spike.session_marker` table + `spike` schema.

### Owner-run teardown steps (tier 3 — destructive, owner executes)

All from repo root, after `source infra/envs/home.env`.

1. Review + apply the spike-module removal (destroys Cloud Run service and
   the two spike SA IAM grants):

   ```bash
   cd infra
   terraform plan -var-file=envs/home.tfvars -var='spike_mcp_image=' -out=home-spike-teardown.tfplan
   # review: expect 0 to add, 0 to change, 4 to destroy
   terraform apply home-spike-teardown.tfplan
   cd ..
   ```

2. Delete the live agent engine (SDK-managed, needs `force=True` — child
   sessions exist):

   ```bash
   uv run --with google-cloud-aiplatform==2.1.0 python - <<'EOF'
   import os
   import vertexai
   from vertexai import agent_engines
   vertexai.init(project=os.environ["PROJECT_ID"], location="europe-west4")
   agent_engines.delete(
       f"projects/{os.environ['PROJECT_ID']}/locations/europe-west4/reasoningEngines/3787430529595342848",
       force=True,
   )
   print("agent engine deleted")
   EOF
   ```

3. Delete the spike AR images (all tags/digests under the repo; they are only
   spike builds):

   ```bash
   gcloud artifacts docker images delete \
     "$REGION-docker.pkg.dev/$PROJECT_ID/service-images/spike-connectivity-mcp" \
     --delete-tags --region "$REGION" --quiet
   ```

4. Drop the spike DB schema (one-time admin session via port 3307, same
   pattern as `sql/admin_apply.py` — sync Connector + psycopg; instance
   `$PROJECT_ID-sessions`, password `SPIKE_DB_PASSWORD` from `home.env` per D7):

   ```bash
   uv run --with cloud-sql-python-connector --with "psycopg[binary]" python - <<'EOF'
   import os
   from google.cloud.sql.connector import Connector
   with Connector() as c:
       conn = c.connect(
           f"{os.environ['PROJECT_ID']}:europe-west4:{os.environ['PROJECT_ID']}-sessions",
           "psycopg", user="postgres", password=os.environ["SPIKE_DB_PASSWORD"],
           db="postgres", port="3307")
       conn.execute("DROP SCHEMA IF EXISTS spike CASCADE")
       conn.commit()
       conn.close()
   print("spike schema dropped")
   EOF
   ```

5. Final verification (read-only, agent can run on request):
   `gcloud run services list` (no spike service), agent engine gone, AR image
   list empty for spike, `terraform plan -detailed-exitcode` clean.

### Teardown evidence (executed 2026-09-06)

- Terraform `home-spike-teardown.tfplan` reviewed (0 to add, 0 to change,
  4 to destroy) and applied by the owner: **success — 4 destroyed** (Cloud Run
  service `spike-connectivity-mcp` + the two spike SA IAM grant sets).
- Agent engine delete: first attempt **failed** — the aiplatform SDK defaults
  to the `us-central1` endpoint and rejects a `europe-west4` resource name
  (400: "The provided location ID doesn't match the endpoint"). Fixed by
  calling `vertexai.init(project=…, location="europe-west4")` before
  `agent_engines.delete(..., force=True)`. **Gotcha 9 (increment 5): the
  engine's resource name alone does not select the endpoint — always
  `vertexai.init` with the region first.** Second attempt succeeded:
  engine `3787430529595342848` deleted (backing LRO
  `…europe-west4/operations/5624665462622126080` completed).
- AR image delete: `gcloud artifacts docker images delete` takes **no
  `--region` flag** (location comes from the image path); first attempt
  rejected the flag. **Gotcha 10: drop `--region` on AR image delete.**
  Second attempt succeeded (operation `0733dd23-…-7010b625663d`).
- Schema drop: the async Connector snippet failed twice (sync `connect()`
  returns a connection that can't be awaited; then `connect_async` hit
  `ConnectorLoopError` — loop mismatch). The proven pattern is the same as
  `sql/admin_apply.py`: **synchronous `Connector()` + `connector.connect(...,
  "psycopg", port="3307")` with `psycopg[binary]`**. **Gotcha 11: use the
  sync Connector + psycopg pattern for one-off admin sessions; the async API
  is loop-bound and brittle in ad-hoc scripts.** Succeeded: `spike schema
  dropped` (run twice, idempotent).
- Final verification (agent-run, read-only, 2026-09-06):
  - `gcloud run services list` (europe-west4): **no services**.
  - AR `service-images` image list: **0 items**.
  - `agent_engines.list()` after `vertexai.init(..., europe-west4)`: **[]**.
  - `terraform plan -detailed-exitcode`: exit 0 — **no drift**.
  - Budget `trial-80pct`: limit 1114 PLN/month, credits included, no 80%
    notification. Remaining recurring cost: only Cloud SQL `db-f1-micro`.

### Increment 5 result: COMPLETE

Phase 1 spike closed: end-to-end objective met under D8 fallback; all spike
resources removed; no drift; costs back to baseline (Cloud SQL only). Source,
plans, sanitized traces, and D8 preserved per the phase-1 plan.