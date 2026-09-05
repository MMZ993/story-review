# Runbook 06 — Phase 1 connectivity spike

Executes `docs-local/plans/phase-1-connectivity-spike.md`. Disposable
resources only; teardown is mandatory after evidence.

Status: IN PROGRESS — increment 1 (interfaces confirmed, tests written).

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

## Increment 4 — Deploy and prove the Agent Engine caller (TODO)

## Increment 5 — Decision gate and cleanup (TODO)
