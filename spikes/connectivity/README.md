# Connectivity spike (Phase 1)

Disposable Agent Engine → authenticated Cloud Run MCP → Cloud SQL proof, per
`docs-local/plans/phase-1-connectivity-spike.md`. Nothing here is production
code; teardown is mandatory after evidence.

Layout (deviation from the plan's `mcp/`/`agent/` names, recorded in Runbook
06: a local top-level package named `mcp` would shadow the `mcp` SDK):

```text
spikes/connectivity/
├── spike_agent/        # agent-side probe core + locked requirements
├── spike_mcp/          # MCP service core (store, SQL store, auth, ASGI app) + locked requirements
├── sql/                # one-time admin bootstrap + ordered migration + grants
├── tests/              # deterministic unit and contract tests
├── Dockerfile          # spike MCP service image (increment 3)
├── deploy-mcp.sh       # build + push the spike image (tier-2)
└── conftest.py         # makes spike_* packages importable from repo root
```

## Local test loop

    make spike-connectivity-test

Tests are fully offline: the store contract runs against the in-memory store
and a fake asyncpg pool, the MCP contract runs over the in-memory MCP
transport with a fake verified principal, HTTP tests use the ASGI test client
with a fake token verifier, and the agent probe uses a fake transport. Real
Cloud SQL access and real ID-token verification happen in the deployed
service (Runbook 06 increments 3–4).
