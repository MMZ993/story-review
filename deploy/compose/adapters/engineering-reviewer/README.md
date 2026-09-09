# Engineering-reviewer local adapter (Phase 5)

Same frozen single-turn reviewer contract as the business-reviewer adapter
(`POST /invoke`, `GET /health`, shared `ErrorEnvelope` mapping), bound to
the engineering-reviewer agent. All contract logic lives in
`agent_kit.adapter`; this package is the binding plus tests.

Deterministic tests: `make engineering-reviewer-adapter-test`.
Real-model tests: `make engineering-reviewer-live-test` (main PC, ADC).
