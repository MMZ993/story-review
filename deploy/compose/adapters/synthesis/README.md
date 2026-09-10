# Synthesis local adapter (Phase 5)

Frozen synthesis invocation contract (`POST /invoke` with the latest
business + engineering pairs, `GET /health`, shared `ErrorEnvelope`
mapping), bound to the synthesis agent. Request/response models and
assembly checks live in `agent_kit.synthesis_input`; the single-turn run
and HTTP shell live in `agent_kit.synthesis_adapter`; this package is the
binding plus tests.

Deterministic tests: `make synthesis-adapter-test`.
Real-model tests: `make synthesis-live-test` (main PC, ADC).
