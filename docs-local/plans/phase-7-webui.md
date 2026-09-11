# Phase 7 — Web UI (minimal chat MVP) plan

## Objective

Implement the minimal web client per **D16**: a thin static HTML/JS page served by a
small FastAPI/uv package (`webui/`), consuming the orchestration API contract
as-is — no server-side changes. Scope: pre-conversation story picker with hover
preview, chat-style dialogue view for PO turns (idempotency-key replay,
single in-flight request), PO-acceptance/finalize path, report download through
regenerated signed URLs. No animations, no design system.

Exit criterion (development-plan.md): the `example-interaction.md` walkthrough
playable end-to-end from a browser against the local compose stack.

Cost: Vertex AI tokens only (turns invoked during gates); Cloud SQL stays
STOPPED — the compose Postgres substitute carries all state, unchanged from
Phase 6.

## Preconditions

- Phase 6 complete and closed (session 38; live integration suite PASS).
- `docs/design/api-contract.md` "Client interaction states" (updated by D16) is
  the authoritative client state machine — the UI implements exactly these
  states and client rules.
- Starting point D16-3: the owner's chat UI in `~/projects/homelab/cv-agent`
  (`src/cv_agent/static/chat.{html,js,css}`, vanilla JS; standalone
  `src/cv_agent/frontend/markdown.js` renderer + vitest/jsdom tests) — chat
  shell and markdown rendering carry over; API calls re-pointed to orchestration
  with idempotency keys; story picker added.

## Increment-0 owner decisions (D17 candidates — settle before increment 1)

1. **Packaging**: `webui/` uv package (`webui` 0.1.0, FastAPI + uvicorn serving
   static files only — no business logic, no DB, no downstream clients;
   orchestration base URL via env `ORCHESTRATION_BASE_URL`) + root-context
   Dockerfile like the other units, wired into compose as a `local`-profile
   service next to orchestration. Per repository-layout.md `webui/` row. Confirm.
2. **JS test tooling**: vitest + jsdom for the frontend JS tests (same setup as
   the cv-agent source project; node-based, dev-only, not shipped in the image).
   Test targets: markdown rendering (carried over), idempotency-key/session-id
   persistence logic, API client state machine (fetch mocked). Confirm.
3. **Reuse mechanics**: copy the needed pieces into `webui/static/` (chat shell
   html/css trimmed to minimal, markdown renderer module, message-rendering
   helpers) — no vendoring of the 3.6k-line chat.js; API layer written fresh
   against api-contract.md. Confirm.
4. **Client persistence**: session id + pending idempotency keys in
   `localStorage` keyed by session id, so a page reload resumes the active
   session (client rule: persist the idempotency key with the in-flight logical
   request). Confirm.
5. **Browser verification**: gates are owner-driven manual walkthroughs in a
   real browser (agent proposes exact steps; owner executes and reports), same
   as live gates; no automated browser automation in this phase. Confirm.

## Deliverables

- `webui/` — uv package: FastAPI app serving `static/`, `/health`, env-driven
  config (orchestration URL only); no CORS needed if the page calls
  orchestration directly (decide: direct browser→orchestration calls from the
  served page — orchestration already exposes the API on the compose network /
  published port).
- `webui/static/` — `index.html` (story picker view + session/chat view),
  `app.js` (state machine: idle → browsing → session active → processing →
  parked/completed), `api.js` (fetch wrapper: Idempotency-Key UUID v4 per
  mutating request, 503 same-key retry with short backoff, error-envelope
  display), `markdown.js` (carried over), `app.css` (minimal usability).
- `webui/tests/frontend/` — vitest suite (markdown, api state machine, key
  persistence).
- Makefile: `webui-test` (deterministic: uv package tests + vitest).
- Compose wiring + Dockerfile.
- Runbook 13 (`docs-local/runbooks/13-webui.md`) — commands and evidence per
  increment, sanitized.

## Implementation increments

### 0. Decisions + skeleton (local, no LLM cost)

- Settle D17 candidates; record in local-decisions.md.
- uv package skeleton + static serving + /health + compose service + Dockerfile
  + `webui-test` target; carry over markdown renderer + its tests; verify the
  page loads against the compose stack (orchestration reachable, health green).

### 1. Story picker + session creation (local + live gate)

- Browsing view: `GET /api/v1/stories` list; select/hover renders story detail
  via `GET /api/v1/stories/{id}` before confirmation.
- Confirm → `POST /api/v1/sessions` with fresh Idempotency-Key; 5-min spinner
  state ("reviewing…"); error-envelope display; 409 active-session handling.
- Live gate: one real session created from the browser over compose (main PC);
  evidence in Runbook 13.

### 2. Chat view — dialogue turns (local + live gate)

- Session view: message list (PO right, facilitator markdown left), input box,
  exactly one in-flight request; `POST /api/v1/sessions/{id}/turns` with the
  key persisted per logical request; 503 same-key retry after short backoff;
  409 SESSION_LOCKED → retry hint, never auto-hammer; turn outcomes
  (continue/park/finalize) drive the UI state; turn `syntheses`/artifacts
  surfaced minimally per api-contract TurnResponse.
- Session resume: on load, if localStorage has an active session id →
  `GET /api/v1/sessions/{id}` history replay.
- Live gate: the example-interaction dialogue arc (re-review turn,
  re-synthesis, continue) from the browser.

### 3. Park / PO acceptance / finalize / report download (local + live gate)

- Parked view: read-only history + "start new session on same story".
- PO acceptance turn (`po_accepted=true`) with synchronous finalize response;
  finalize retry endpoint surfaced for the finalizing state.
- Completed view: report links via fresh `GET /api/v1/sessions/{id}/report`
  signed URLs; download over the URL as returned (fake-gcs locally).
- Live gate: full browser session from story pick to downloaded report over
  compose (mirrors the Phase 6 increment-4 gate, now through the UI).

### 4. Exit gate — example-interaction walkthrough end-to-end + close

- Owner-driven walkthrough of `example-interaction.md` from the browser against
  `agents-compose-up`: story pick → dialogue arc → park or accept → report
  download; idempotency replay checked (reload mid-logic / same-key retry).
- All regression suites green; independent read-only review of the phase diff;
  phase marked COMPLETE in development-plan.md; Runbook 13 completion review.

## Verification gates

- Every increment: deterministic checks (uv package tests + vitest, no LLM
  cost) plus browser live gates on the main PC where the increment touches
  agent-facing behavior; all Phase 6 baseline suites stay green.
- Sanitized evidence into Runbook 13; identifier check before commits with
  evidence.

## Out of scope (per D16)

- Any orchestration/API server-side change; styling beyond basic usability;
  animations; multi-session management UI; authentication on the webui;
  browser-automation test harness; deployment beyond compose (Phase 8).

## Risks and controls

- **Idempotency-key discipline**: keys generated client-side (UUID v4) and
  persisted with the logical request before the fetch fires; unit tests for
  the retry path (503 → same key) against a mocked fetch.
- **Long request UX**: session creation up to 5 min, turns up to the lease
  window — spinner + disabled input; fetch has no client timeout (server
  deadline governs); abort on navigation only.
- **Signed-URL host reachability locally**: URLs are rewritten by orchestration
  to `ORCH_GCS_PUBLIC_URL` (fake-gcs, compose) — browser must reach that host
  (published port); verify at increment 3, record any local-only substitution.
- **chat.js reuse scope creep**: only shell/markdown carry over per D16-3; the
  API layer is new code against the contract.

## References

- `docs/design/api-contract.md` (endpoints + client interaction states),
  `docs/design/data-flow.md` (flows 1–4), `docs/operations/repository-layout.md`
  (`webui/`), `docs/design/example-interaction.md` (exit-gate walkthrough)
- `docs-local/local-decisions.md` D16 (Web UI decision + D16-3 starting point)
- Source: `~/projects/homelab/cv-agent/src/cv_agent/static/` and
  `frontend/markdown.js` + its vitest tests
