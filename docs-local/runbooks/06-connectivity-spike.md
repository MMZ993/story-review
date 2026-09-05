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

## Increment 2 — Database migration and IAM db access (TODO)

## Increment 3 — Build and provision the Cloud Run MCP service (TODO)

## Increment 4 — Deploy and prove the Agent Engine caller (TODO)

## Increment 5 — Decision gate and cleanup (TODO)
