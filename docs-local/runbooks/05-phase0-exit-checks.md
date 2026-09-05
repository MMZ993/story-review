# Runbook 05 — Phase 0 exit checks: Vertex AI smoke test + D1 evidence

Closes Phase 0: a minimal local ADK agent calls Gemini via Vertex AI using ADC,
with no deployed infrastructure. Records the trial-account availability checks
from local-decisions.md D1.

Status: EXECUTED 2026-09-05 — smoke test passed; Phase 0 exit criteria met
(except the two Agent Engine bullets deferred to the Phase 1 spike by design).

## Scope

- `scripts/smoke_vertex.py` — in-process ADK `LlmAgent` + `InMemoryRunner`;
  model `gemini-2.5-flash` (override via `SMOKE_MODEL`); auth via ADC only.
- `Makefile` skeleton with `smoke-vertex`, terraform convenience targets, and
  stubs for `compose-up`/`compose-down` (Phase 4).
- D1 check mapping:
  1. *billing active with trial credits applied* — evidenced at Runbook 01
     (billing linked, budget on trial credits); re-confirm below.
  2. *Agent Engine + Vertex AI available in `europe-west4` on a trial account* —
     Vertex AI: proven by the smoke test itself. Agent Engine resource
     availability: proven by the Phase 1 spike (creating an Agent Engine
     resource now would be a billable deployment with no other purpose);
     recorded there.
  3. *`adk deploy agent_engine` works with local ADC* — deliberately deferred
     to the Phase 1 spike, which deploys trivial throwaway services anyway.

## 1. Confirm billing is active (read-only)

```bash
source infra/envs/home.env
gcloud billing projects describe "$PROJECT_ID" \
  --format='value(billingEnabled,billingAccountName)'
```

Expect `True` and the billing account id (already linked in Runbook 01).

## 2. Run the smoke test (tiny Vertex AI token cost)

```bash
make smoke-vertex
```

Expected output ends with `model replied: phase-0-exit-ok` (the model may add
punctuation; the check is that a non-empty response arrives through ADK) and
`phase 0 exit check: PASS`. Exit code 0.

## 3. Record D1 evidence

Record below: billing confirmation, the smoke output, model/region used, and
the deferral notes for the two Agent Engine bullets. Tick the Phase 0 checklist
item in `docs-local/runbook.md`.

## Gotchas

- ADK `InMemorySessionService.create_session` requires `user_id` even for a
  throwaway session.
- ADK requires `GOOGLE_GENAI_USE_VERTEXAI=true`; with the API-key path unset,
  a missing value fails with a client error rather than falling back.
- If ADC is missing/expired (`gcloud auth application-default print-identity-token`
  fails), re-run `gcloud auth application-default login` with all consent
  scopes ticked (Runbook 01).

## Evidence

- 2026-09-05 — billing check: `gcloud billing projects describe` returned
  `billingEnabled=True` with the linked billing account (D1 check 1
  re-confirmed; identifiers stay in `home.env`).
- 2026-09-05 — `make smoke-vertex` (first run): failed with
  `TypeError: InMemorySessionService.create_session() missing 1 required
  keyword-only argument: 'user_id'` — ADK API detail; fixed by passing
  `user_id="smoke-user"`. Failure recorded as evidence.
- 2026-09-05 — `make smoke-vertex` (second run): **PASS**. `uv run --with
  google-adk` installed 56 packages and selected CPython 3.13.3; model
  `gemini-2.5-flash` in `europe-west4` via ADC replied exactly
  `phase-0-exit-ok` through the ADK `InMemoryRunner`. (Vertex AI prints a
  non-fatal advisory about automatic function calling — informational only.)
- D1 disposition: checks 1–2 evidenced (billing; Vertex AI availability on
  trial in `europe-west4`); Agent Engine availability + `adk deploy
  agent_engine` deferred to the Phase 1 spike by design.

