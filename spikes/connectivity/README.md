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
├── deploy-agent.sh     # stage + deploy Agent Engine caller (tier-2)
├── run-agent-trace.sh  # two-request persist/restore proof (request usage)
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

## Agent Engine proof (Increment 4)

After the Cloud Run service is deployed with its service URL audience, run the
owner-approved tier-2 deployment procedure in Runbook 06 §Increment 4:

```bash
spikes/connectivity/deploy-agent.sh
spikes/connectivity/run-agent-trace.sh <agent-engine-id>
```

The trace makes separate Agent Engine persist and restore requests, then exits
nonzero unless the structured responses prove the exact generated session ID,
marker, and correlation ID were persisted and restored. It retains raw local
outputs in a printed `/tmp/spike-trace.*` directory for sanitization; record
only sanitized values and the correlation ID in the runbook.
