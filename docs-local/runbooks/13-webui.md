# Runbook 13 — Web UI (Phase 7)

Environment: owner's main PC (ADC + Vertex available; compose stack local).
Cloud SQL stays STOPPED throughout Phase 7 — orchestration state lives in the
compose `postgres` substitute, as in Phase 6. Plan:
`docs-local/plans/phase-7-webui.md`; decisions D16, D17 (+ amendment 1).

Verification-state log (append-only):

## Increment 0 — skeleton: package, static shell, /api proxy, tests, compose

**Status: COMPLETE (session 40, 2026-09-15; browser gate PASS).**

Owner decision opening the phase (**D17 amendment 1**): D17-1's "browser
calls orchestration directly" is unworkable (no CORS on orchestration, D16
forbids adding it; no persistent orchestration endpoint existed). The webui
app gains a thin same-origin `/api` reverse proxy (chosen for its fit to the
GCP deployment shape: one HTTPS LB path-routing `/api` → orchestration);
orchestration becomes a compose service as the proxy target. Recorded in
local-decisions.md.

Commands run (all local, no cloud actions, Cloud SQL STOPPED):

    make webui-test    # 7 passed (uv package) + 2 passed (vitest)
    docker build -f webui/Dockerfile -t webui-dev-test .        # ok
    docker run --rm -d --name webui-smoke -p 127.0.0.1:8121:8080 \
      -e ORCHESTRATION_BASE_URL=http://127.0.0.1:1 webui-dev-test
    curl -s http://127.0.0.1:8121/health           # {"status":"ok"}
    curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8121/   # 200
    curl -s http://127.0.0.1:8121/api/health
    # -> 503 ORCHESTRATION_UNREACHABLE (retryable) — proxy error path ok
    for p in / /app.js /app.css /markdown.js /vendor/marked.esm.js; do
      curl -s -o /dev/null -w "$p %{http_code}\n" http://127.0.0.1:8121$p;
    done   # all 200
    docker rm -f webui-smoke && docker rmi webui-dev-test        # cleaned up

Delivered:
- `webui/` uv package 0.1.0: `config.py` (strict env, single mandatory
  `ORCHESTRATION_BASE_URL`), `main.py` (app factory: `/health` liveness,
  static shell at `/`, `/api/{path}` pass-through proxy — method/path/query/
  body + Content-Type/Idempotency-Key/X-Correlation-Id forwarded, upstream
  status/body/correlation-id returned, `ORCHESTRATION_UNREACHABLE` retryable
  503 on connection errors).
- `webui/static/`: `index.html` (increment-0 shell: header with live
  orchestration status line, picker/session placeholders, import map),
  `app.js` (loads `/api/health`, displays reachability), `app.css` (minimal
  usability), `markdown.js` (carried over unchanged from cv-agent per
  D16-3/D17-3), `vendor/` (dompurify 3.4.13 / marked 18.0.9 / remend 1.3.0
  ESM dist files — the libraries' real source, vendored, no bundler).
- Tests: `webui/tests/test_app.py` (7 — health, static root, config
  strictness, GET/POST proxy forwarding incl. key header + query, upstream
  status/error-envelope passthrough, unreachable→503) with an httpx
  MockTransport upstream; `webui/tests/frontend/markdown.test.js` (2 —
  carried-over sanitizer tests, links de-fanged for the capstone context).
- `webui/package.json` + lock (dev-only vitest+jsdom; `node_modules/`
  gitignored), `webui/Dockerfile` (root-context, dataset guard, non-root),
  Makefile `webui-test` target, `.gitignore` node_modules entry.
- Compose: `webui` service (`local` profile, host port
  `127.0.0.1:${WEBUI_PORT:-8120}`, proxies to `http://orchestration:8080`);
  `orchestration` service (`local-agents` profile, host port
  `127.0.0.1:${ORCHESTRATION_PORT:-8130}`, compose-postgres DSN, compose
  service URLs, ADC bind mount like the adapters, `ORCH_GCS_PUBLIC_URL` →
  fake-gcs HTTPS host port).

Gotchas learned:
- **Compose Postgres namespace clash**: the default database in the compose
  postgres is the facilitator's ADK session backend, which already owns a
  `sessions` table — orchestration migration 0001 (`create table if not
  exists sessions`) silently skips it and then fails on a `turns` FK
  (`column "session_id" ... does not exist`). Fix: orchestration uses a
  **separate `orchestration` database** in the same container (compose
  `ORCH_DB_DSN` updated; `createdb` before first migration run).
- **MCP 421 in-network**: with `*_SERVICE_URL` unset, the MCP SDK's
  DNS-rebinding protection defaults the app host to `127.0.0.1` and rejects
  any other Host header with 421 — so in-network calls like
  `http://story:8080/mcp` (Host `story:8080`) fail while host-port calls
  (`127.0.0.1:8101`) pass (why the Phase 6 host-side gates never saw it).
  Fix: compose sets `STORY/ARTIFACT/REPORT_SERVICE_URL` to the in-network
  URLs (host then matches → protection does not auto-enable; harmless since
  local auth is disabled). In Cloud Run these are set anyway (audience), so
  this is local-only.
- Orchestration's `/health` lives **outside** the `/api` prefix — the webui
  status probe uses `GET /api/v1/stories?limit=1` (real readiness signal)
  instead of a health path.
- Orchestration (compose service) crashes at startup if its database does
  not exist yet — create the DB + run migrations **before** the first
  `agents-compose-up` that includes it (ordering in the gate commands
  below).
- `StaticFiles(html=True)` mounted at `/` serves assets at their bare paths
  (`/app.js`, not `/static/app.js`) — index.html references use the bare
  form.
- Makefile recipe already `cd webui` — `npm --prefix webui` inside it
  resolves to `webui/webui` (silent wrong-directory failure); run npm
  without the prefix after the cd.
- httpx `MockTransport` handlers must use `httpx.Response(...)`; requests
  expose `.content` (no `.json()` helper).

Browser gate (owner-driven, D17-5) — **PASS** (2026-09-15):

    # one-time database setup (idempotent thereafter):
    docker compose --profile local --profile local-agents --env-file env/.env \
      exec -T postgres createdb -U facilitator orchestration
    docker run --rm --network story-review_default \
      -v "$PWD/deploy/cloud-sql:/m:ro" \
      -e DATABASE_URL=postgres://facilitator:facilitator@postgres:5432/orchestration \
      postgres:16 bash /m/run-migrations.sh
    make agents-compose-up   # brings up the full stack incl. orchestration + webui

Host-side checks before handing over: `curl 127.0.0.1:8130/health` →
{"status":"ok"} with all four dependencies reachable;
`curl -o /dev/null -w %{http_code} 127.0.0.1:8120/api/v1/stories` → 200.
Owner in the browser at `http://127.0.0.1:8120/`: page loads, header shows
**"orchestration: reachable"** (verbatim report in chat). Stack left up for
the increment-1 session; `agents-compose-down` when done with it.

Increment-0 independent review (fresh read-only subagent, after the browser
gate): **1 Critical + 1 Important + minors — all fixed in-session.**

- **Critical**: the proxy's httpx client used the default 5 s timeout — a
  long turn (up to the 5-minute request deadline) would surface as a
  retryable `ORCHESTRATION_UNREACHABLE` 503 while orchestration is still
  processing, inviting a same-key retry against the live turn. Fixed:
  `timeout=httpx.Timeout(None)` (server deadline governs) + a pinning test.
- **Important**: `/api/%2e%2e/health` (raw dot-segment traversal) escaped
  the /api scope via httpx path normalization. Fixed: normpath guard → 404
  (+ test). Gotcha: curl *without* `--path-as-is` decodes/normalizes such
  paths client-side, so manual checks must use `--path-as-is` to exercise
  the guard (verified live: 404).
- Minors fixed: misleading `/health` docstring (orchestration health is
  outside /api); new tests pinning the forwarded-header allowlist
  (Cookie/Authorization/arbitrary client headers are never forwarded) and
  405 for non-forwarded methods. Deferred minor: `npm ci` in `webui-test`
  hits the registry (dev-only tooling per D17-2 — acceptable).

Post-fix verification: `make webui-test` **11 passed + 2 vitest passed**;
webui container rebuilt and live: `GET /api/v1/stories?limit=1` via proxy
→ 200, raw traversal → 404; compose contract **20 passed** (regression).

## Increment 1 — story picker + session creation (2026-09-15, session 41)

Scope per `docs-local/plans/phase-7-webui.md` increment 1: browsing view
(`GET /api/v1/stories`, hover/focus preview via `GET /api/v1/stories/{id}`,
cached), confirm → `POST /api/v1/sessions` with a fresh UUID-v4
`Idempotency-Key`, "reviewing…" spinner (5-min server deadline), error-envelope
display, `409 SESSION_ACTIVE` hint.

Delivered:

- `webui/static/api.js` — fresh API client per D17-3 (fetch wrapper, uuidv4,
  key persistence under `pending:create-session` before the fetch fires,
  503 same-key retry with short backoff and bounded attempt budget,
  non-2xx error-envelope normalization; fetchImpl/storage/sleep injectable).
  Body carries `requested_formats: ["md","pdf"]` (contract requires a
  non-empty list; no format picker in D16 scope).
- `webui/static/app.js` — picker wiring: story list render, hover/focus
  preview (textContent only), one in-flight confirm with disabled button +
  spinner, session id persisted under `session:id` for increment-2 resume,
  409 active-session hint; header reachability probe kept from increment 0.
- `index.html` picker section + `app.css` additions.
- `webui/tests/frontend/api.test.js` — 13 behavior tests (test-first, written
  against a missing module and confirmed failing): uuidv4 shape, key
  persistence/clearing/reuse (lost-response replay), 503 same-key retry +
  attempt budget, 409/404/422 envelope pass-through without retry.

Test-first gotcha: the first version asserted a `{session:{id}}` response
shape; the contract's `CreateSessionResponse` is **flat**
(`session_id`, `state`, `facilitator_reply`, …) — mocks and app.js corrected.
Also `GET /stories` rows key on `story_id` (not `id`), verified live against
the compose orchestration before the gate.

Verification: `make webui-test` → **pytest 11 passed + vitest 15 passed**
(13 new). Compose regression pending; baseline suites re-run before commit.

Gate commands (approved in chat; webui image bakes `static/`, so a rebuild
is required after static changes):

    docker compose -f deploy/docker-compose.yml --profile local build webui
    docker compose -f deploy/docker-compose.yml --profile local up -d webui

Host-side pre-checks: `GET :8120/health` → {"status":"ok"}; picker view in
the served index; `GET :8120/api/v1/stories` via proxy → 45 stories;
`GET :8120/api/v1/sessions` → empty (no active sessions to collide with).

Browser gate (owner-driven, D17-5): picker list + hover preview + one real
flow-1 session creation (≈4 Vertex calls) + reload → same story → 409
active-session hint. Result: **PASS** (2026-09-15):

- Picker renders 45 stories through the proxy; hover preview shows the
  sanitized-markdown story detail; filter + foldable list verified.
- Real flow-1 from the browser on story-04 → `201`; durable session
  `sess-0e9c…` (state active, formats md+pdf) confirmed via
  `GET /api/v1/sessions` through the proxy. Owner report verbatim:
  "session sess-0e9c… created — chat
  arrives in increment 2".
- 409 path: re-selecting story-04 → envelope surfaced with the
  active-session hint (owner report verbatim, see below).

Live-gate findings fixed in-session (third redeploy):

- **Error path wrote to a hidden element**: `startSession` failures were
  rendered into the session-view `#status` (hidden while the picker is
  shown) — the 409 was invisible ("shows same text for a fraction of a
  second and nothing happening", owner report). Fixed: errors go to the
  picker's visible `#picker-status`; only success switches the view.
- **Wrong error code matched**: the hint keyed on `SESSION_ACTIVE`, but
  the live envelope is `STORY_SESSION_ACTIVE` (verified via the proxy:
  `409 {"code":"STORY_SESSION_ACTIVE","retryable":false}`). Fixed the
  comparison. Final owner report verbatim: "the story already has an
  active session; restore it instead (this story already has an active
  session — finish it before starting a new one)".

Layout iterations (owner feedback, same session): side-by-side list
+ preview → two-column with search filter + wide preview + markdown
preview → (final, implemented by delegated gpt-5.6-terra subagent)
header row with the confirm button, foldable `<details>` story list with
live summary "stories (N) — selected: <title>", compact inline
radio rows (fixing radio-stacked-above-label), full-width preview
below. Compose contract regression: **20 passed**; `make webui-test`
final: **pytest 11 + vitest 15** (13 new for api.js).

Owner layout feedback after first look (session 41): picker list too
narrow (titles wrapped awkwardly), preview squeezed, button stealing
preview width, preview showed raw markdown. Reworked in-session:
two-column picker (filter + list + button stacked left, wide preview
right), search filter over the loaded list (client-side, selection
preserved), preview rendered via the shared sanitized markdown renderer.

## Increment 2 — chat view: dialogue turns + session resume (2026-09-15, session 42)

**Status: COMPLETE (browser gate PASS).**

Delivered (test-first; all new tests confirmed failing before implementation):

- `webui/static/api.js` — extracted shared `postWithIdempotentKey()` core
  (createSession now built on it); added `fetchSession()` (GET
  /sessions/{id}) and `postTurn()` (POST /sessions/{id}/turns; one pending
  key per session under `pending:turn:{sessionId}` persisted before the
  fetch — exactly one in-flight logical request per session — re-used on
  503 same-key retry and lost-response replay, cleared on any definitive
  outcome; `po_accepted:true` sends `{po_accepted:true}` with no message
  per the contract).
- `webui/static/chat.js` (new module — session view, keeps app.js under the
  file-size guideline) — history replay from `SessionDetail.turns` (PO
  messages plain-text right, facilitator replies sanitized-markdown left,
  meta line "turn N — open issues: k · synthesis: art-… vN · outcome: …"),
  session header `story — state — facilitator turns n/10`, optimistic PO
  bubble + single in-flight turn (composer disabled while processing),
  409 SESSION_LOCKED retry hint (new request, never auto-hammer), park /
  finalize disable the composer with read-only notes (dedicated parked and
  completed views are increment 3).
- `webui/static/app.js` — boot resumes `localStorage["session:id"]` via
  `openSession` (history replay from GET /sessions/{id}); 404 clears the
  stale id and falls back to the picker; successful session creation now
  opens the chat view directly.
- `index.html` composer form (textarea + send button) + `app.css` message
  meta / session-header / composer styles.
- Tests: `api.test.js` +9 (fetchSession, postTurn key persistence/reuse,
  503 same-key retry, 409/422 no-retry table incl. SESSION_LOCKED /
  SESSION_READ_ONLY / DELEGATION_VALIDATION); `chat.test.js` +8 (jsdom:
  history replay incl. acceptance-action bubble, parked-composer disable,
  404 routing, optimistic bubble + in-flight disable, empty-message guard,
  SESSION_LOCKED hint).

Verification: `make webui-test` → **pytest 11 passed + vitest 32 passed**
(was 15). webui image rebuilt + redeployed (static files baked in);
`GET :8120/health` ok, `/chat.js` served.

Test-infra gotcha (jsdom): `dispatchEvent(new Event(...))` fails with a
realm TypeError — events must be constructed from the jsdom window
(`new document.defaultView.Event(..., {cancelable: true})`).

Browser gate (owner-driven, D17-5): result **PASS** (2026-09-15):

- Substituted gate story: the plan said to gate against the live story-04
  session, but the owner's browser held a **story-02** session
  (`sess-df6d…`, created from the picker earlier in the session); story-02
  gates the chat behavior identically. Session list at gate time: 4 active
  (story-01, -02, -04, -06) — story-01/-02 created during owner testing;
  each creation is real Vertex spend, and park/acceptance UI only arrives
  in increment 3, so no further test sessions should be created.
- **Resume/history replay PASS**: opening the page rendered the story-02
  flow-1 opening turn from GET /sessions/{id} (header
  "story-02 — active — facilitator turns 1/10", facilitator markdown,
  meta "turn 1 — open issues: 10 · synthesis: art-… v1 · outcome:
  continue").
- **Dialogue turns PASS (3 turns)**: turn 2 (business clarifications:
  metrics, roadmap contribution, analytics events) → open issues 10→7,
  synthesis v2, header 2/10; turn 3 (engineering clarifications: PSP API
  contract, idempotency keys, error granularity, logging, SDK failure
  mode) → open issues 7→4, synthesis v3, header 3/10. Facilitator replies
  markdown-rendered; resolution summaries accurate per turn.
- **Reload-resume PASS**: mid-conversation reload replayed all turns from
  the server, composer re-enabled.

Observation (no action): each synthesis version carries a fresh artifact
id (v1 art-e5e2…, v2 art-efdc…, v3 art-e866…) — consistent with the
artifact model (per-version artifacts), surfaced correctly by the meta
line.

## Increment 3 — park / PO acceptance / finalize / report download (2026-09-15, session 42)

**Status: COMPLETE (browser gate PASS; design defect recorded as
future-extensions Item E).**

Delivered (test-first; all new tests confirmed failing before implementation):

- `webui/static/api.js` — `fetchReport()` (GET /sessions/{id}/report) and
  `finalizeRetry()` (POST /sessions/{id}/finalize via the shared
  idempotent-POST core; key scope `pending:finalize:{id}`, 503 render
  failure retried with the same key, 409 NOT_FINALIZING/SESSION_READ_ONLY
  definitive).
- `webui/static/messages.js` (new) — message-list rendering extracted from
  chat.js (file-size guideline): PO plain-text bubbles, facilitator
  sanitized-markdown bubbles + meta line, full history replay.
- `webui/static/chat.js` (rewritten as view controller) — accept-and-finalize
  control in the composer (explicit action + confirm dialog; sends
  `{po_accepted:true}` with no message per contract), parked view (read-only
  note + "start a new session on this story" → host callback), finalizing
  view (retry-finalize control over POST /finalize), completed view (report
  links from the finalize TurnResponse or persisted `SessionDetail.reports`
  on resume + "regenerate report links" over GET /report).
- `webui/static/app.js` — parked-restart routing (clears `session:id`,
  returns to the picker with the same story preselected); picker listeners
  single-wired (re-entry via restart would have double-wired the confirm
  button — two sessions per click).
- `index.html` accept button / actions / report-links elements +
  `app.css` additions.
- Tests: `api.test.js` +3 (fetchReport incl. 409 REPORT_NOT_READY;
  finalizeRetry key persistence, 503 same-key retry, 409 NOT_FINALIZING);
  `chat.test.js` +5 (acceptance turn → report links; confirm-dismissed
  guard; parked restart callback; completed persisted links + regenerate;
  finalizing retry control).

Test-infra gotchas (jsdom): `confirm` is not defined on the node global
(define before spying); events must be constructed from the jsdom window
(carried over from increment 2).

Verification: `make webui-test` → **pytest 11 + vitest 42** (was 32);
`make compose-contract-test` → **20 passed**. webui image rebuilt +
redeployed.

Browser gate (owner-driven, D17-5) — finished the live story-02 session
(`sess-df6d…`, turns 1–3 from the increment-2 gate): result **PASS**:

- Reload → completed-state readiness: composer + accept control on the
  active session at 3/10.
- Accept & finalize (confirm dialog) → synchronous finalize: "(accepted
  the report)" bubble, header → completed, report links (.md/.pdf),
  composer disabled/hidden, regenerate control present.
- Report downloaded over the signed fake-gcs HTTPS URL
  (`ORCH_GCS_PUBLIC_URL=https://127.0.0.1:9026`, host-published — the
  plan's signed-URL reachability risk holds; self-signed cert warning
  accepted in-browser). **Both formats (.md and .pdf) downloaded**
  (owner-confirmed).
- Reload-resume of the completed view **PASS** (owner-confirmed): links
  persisted; "regenerate report links" produced fresh signed URLs.

Design defect found at the gate (owner decision: record as design change,
deferred past Phase 7 — future-extensions **Item E**): the finalized
review was self-contradictory — B-1/B-2 listed as resolved (turn 2) *and*
as remaining-open. Root cause: the turn-3 facilitator delegation re-used
resolved ids (B-1/B-2) for new concerns ("formalize acceptance criteria")
without a re-open resolution; `aggregate_resolutions` (latest recorded
disposition) and `remaining_open_issues` (latest delegation open list) are
both faithful, and the contract permits the overlap (no `reopened`
disposition; no FinalizedReview consistency rule). Webui/orchestration
code unchanged — the artifact faithfully renders contradictory agent data.

Park view: jsdom-tested only this increment — parking from the UI requires
the facilitator's 10-turn gate (~7 more Vertex turns on the story-02
session was judged not worth it); live park verification folds into the
increment-4 exit walkthrough if the arc includes park.

## Item E live gate — issue-identifier lifecycle (2026-09-16, session 43)

Implementation session (D18): `reopened` disposition + shared
`latest_resolutions` helper (review_schemas 0.5.0), `decision_state`
turn-request extension rendered as "Current decision state", adapter
identifier-lifecycle rule in `validate_turn_output` (incl. same-turn
self-contradiction, review finding 1) via the corrective re-prompt loop,
`FinalizedReview` backstop → new `FINAL_REVIEW_INVALID` (503
non-retryable, rolls back to `active`), facilitator prompt rules. All
deterministic suites green (review-schemas 161, agent-kit 98,
orchestration 92+11s, facilitator-adapter 3+1s, webui 44); independent
review Ready-to-proceed with findings fixed (D18 amendments 1–2).
Commits: docs `592dd85` (frozen cherry-pick `7c8b9cf`), code `e58bb7a`,
docs-local `0535b1c`.

In-session UI addition (owner request, tested vitest 44): persistent
"choose another story" control in the session view (every state, clears
`session:id` only; in-flight confirm guard) — the resume boot previously
had no way back to the picker.

Live gate (owner-driven, compose stack rebuilt with the new
orchestration/facilitator images; new code verified inside both images;
result **PASS**):

- New session on **story-09** (free story; 01/04/06 still hold active
  slots, 02 completed). Turn 1: 10 open issues.
- Turn 2 (PO clarifications: acceptance criteria, metrics, failure UX):
  facilitator resolved B-1/B-2/B-3/E-4 — 10 → 6 open; delegation both;
  turn meta consistent.
- Turn 3 (withdrawal of the failure-UX clarification): facilitator
  **re-opened B-3 and E-4** (explicitly, in the reply prose too), gave
  newly identified concerns **fresh ids E-7/E-8/E-9** (no id reuse — the
  prompt rule working), resolved C-1 as a consequence; open count back up
  6 → 9(+). No 422 DELEGATION_VALIDATION — the model complied on the
  first try with the decision-state context (the root-cause fix
  demonstrably sufficient in this run).
- Turn 4: PO acceptance with open issues → synchronous finalize, report
  downloaded over signed fake-gcs HTTPS.
- Report consistency **verified** (owner-pasted, verbatim below trimmed
  to the decision rows): Resolutions shows `B-3 — reopened (turn 3)`,
  `E-4 — reopened (turn 3)` (overriding turn-2 resolved), B-1/B-2/C-1
  resolved; Remaining open lists B-3, B-4, E-1…E-9 — every remaining id
  is never-resolved or reopened; **no resolved/accepted id remains
  open**. The story-02 contradiction class is closed.

Item E exit criteria: schema/design + frozen cherry-pick ✓, shared
validators + tests ✓, orchestration stamping/aggregation ✓, live
acceptance-with-open-issues consistent finalized review ✓ — **Item E
closed**.
