# Connectivity spike (Phase 1)

Disposable Agent Engine → authenticated Cloud Run MCP → Cloud SQL proof, per
`docs-local/plans/phase-1-connectivity-spike.md`. Nothing here is production
code; teardown is mandatory after evidence.

Layout (deviation from the plan's `mcp/`/`agent/` names, recorded in Runbook
06: a local top-level package named `mcp` would shadow the `mcp` SDK):

```text
spikes/connectivity/
├── spike_agent/        # agent-side probe core + locked requirements
├── spike_mcp/          # MCP service core + locked requirements
├── sql/                # (later increment) session-marker migration
├── tests/              # deterministic unit and contract tests
└── conftest.py         # makes spike_* packages importable from repo root
```

## Local test loop

    make spike-connectivity-test

Tests are fully offline: the store is in-memory, the MCP contract runs over
the in-memory MCP transport with a fake verified principal, and the agent
probe uses a fake transport. Cloud SQL and real ID-token verification are
later increments (Runbook 06).
