# Business-reviewer local adapter (Phase 5)

Wraps the real business-reviewer ADK agent (`agents/business-reviewer`,
repo prompt + immutable `config.yaml`) behind the frozen single-turn
reviewer invocation contract from the Phase 5 plan appendix:

- `POST /invoke` — request `{story, previous_review?, extra_context?}`
  (`agent_kit.reviewer_input.ReviewerRequest`) → response
  `{report, agent_version, prompt_sha256}`.
- `GET /health` — liveness with agent version.
- Failures use the shared `ErrorEnvelope` taxonomy: request-shape and
  output-validation failures are non-retryable `VALIDATION_ERROR` (no
  corrective re-prompt for reviewers, D13-3); model/transport failures
  after ADK retries map to retryable `UPSTREAM_UNAVAILABLE`.

Layout: `assembly.py` (pure request/response agreement checks + stamping),
`runner.py` (the single-turn ADK run — the only model I/O), `app.py` (the
FastAPI shell + error mapping). Compose wiring lands with the
`local-agents` profile at increment 4.

Deterministic tests: `make business-reviewer-adapter-test`.
Real-model tests: `make business-reviewer-live-test` (main PC, ADC).
