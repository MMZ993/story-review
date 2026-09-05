# Connectivity spike tests (Phase 1, increment 1)

Behavior-oriented, deterministic tests for the disposable connectivity spike:

- `test_store.py` — session-marker store contract (validation, persist-once,
  restore, not-found).
- `test_contract.py` — MCP service contract over the in-memory MCP transport,
  including the authenticated-caller requirement (fake verified principal
  injected by the test adapter; the authorization boundary itself stays on).
- `test_agent_probe.py` — the agent-side probe carries a caller-generated
  correlation ID to the MCP request and exposes the tool result without
  interpretation.

Run from the repository root:

    make spike-connectivity-test
