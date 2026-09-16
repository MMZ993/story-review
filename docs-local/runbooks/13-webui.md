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

## D19 live gate — issue catalog (2026-09-16, session 44)

Session goal: live evidence for D19 (facilitator-minted issue with a
same-turn descriptor surviving into the finalized review's Issues
section; no bare ids anywhere). The gate surfaced — and closed — two
real D19 implementation gaps before passing.

### Findings fixed in-session (root causes, evidence)

1. **Serving-safe mirror gap (Critical).** The facilitator emits its
   turn through Vertex structured output against the ADK
   `output_schema=ServingSafeFacilitatorTurnOutput` — and that mirror
   predated D19: it had no `new_issues` field. The model was
   *structurally incapable* of emitting the IssueDraft, which explains
   every observed symptom across three sessions: F-1 described in
   `reply` prose but never in an array; corrective re-prompts never
   recovering; **byte-identical replies (same md5) on all three
   attempts per turn** at temperature 0 (identical schema + input →
   identical constrained decoding output — replay theory was a red
   herring; the model's input never differed *effectively* because the
   field could not exist). Diagnosis path worth remembering: the
   adapter's ADK session events (facilitator DB, `events` table) hold
   the exact model replies — md5-comparing the three attempts per turn
   is what pinned it. Fix: `MirrorIssueDraft` + `new_issues` on the
   mirror (`agent_kit/llm_output.py`), test-first
   (`test_facilitator_mirrors.py`, agent-kit 103 → 104).
2. **Catalog sourcing gap (Important).** First acceptance attempt on
   story-05 failed the D19 completeness backstop
   (`FINAL_REVIEW_INVALID`: "issues referenced without a catalog entry:
   B-1, B-4, E-2, E-4, E-5, E-8") — exactly the ids resolved at turn 2
   and dropped by the post-clarification re-synthesis. The catalog was
   sourced from the *latest* synthesis only; the design never accounted
   for resolved-and-dropped ids still referenced by the aggregate
   Resolutions. Rollback to `active` worked as designed; acceptance was
   retried after the fix. Owner decision: **union across all synthesis
   versions the session produced, latest version winning** (better
   report quality over lazy backfill). Docs: `docs/design/schemas.md`
   catalog paragraph updated (atomic docs commit + frozen cherry-pick
   due). Code: `issue_catalog(synthesis_reports, turns)`;
   `run_flow3` fetches each turn's `produced_artifacts` synthesis
   (deduped, turn order), fallback to the latest reference when turns
   carry none. Test-first
   (`test_issue_catalog_unions_synthesis_versions_latest_wins`;
   orchestration 95 → 96).
3. **Supporting hardening (kept)**: facilitator prompt `new_issues`
   bullet gained a worked example + "prose in `reply` alone is not
   enough"; the descriptor-validator rejection message now carries the
   inline JSON shape (reaches both the 422 body and the corrective
   re-prompt automatically). Neither could fix gap 1, but both make
   first-attempt minting more likely and corrections actionable.

### Gotchas recorded

- Transient host-network outage to `oauth2.googleapis.com` (ADC token
  refresh) mid-gate → facilitator 503s; recovered on its own. Distinguish
  outage-driven 422/503s from validation 422s via the adapter log before
  debugging behavior.
- ADK session dialogue memory keeps rejected replies (by design,
  observability.md); a session whose memory holds a rejected reply could
  not be recovered by corrective re-prompts *while the mirror gap
  existed* — untested whether post-fix corrections now recover such a
  session (the gate passed on a first-attempt mint; fine either way).
- Facilitator adapter's ADK events are queryable read-only via the
  compose Postgres (`facilitator` DB) — the fastest diagnosis path for
  "what did the model actually say".

### Webui debt observed (client-side only; server correct in each case)

1. Optimistic PO bubble persists after a failed turn (cleared only on
   refresh).
2. Stale error banner survives switching sessions via "choose another
   story".
3. Refresh during an in-flight turn drops the pending message from the
   view and re-enables send; the localStorage idempotency key may be
   lost mid-fetch → possible double turn. All three are candidates for
   the increment-4 pass or a recorded known-issue list.

### Gate evidence (owner-driven, story-05, **PASS**)

- Fresh session on story-05 (`sess-d37f0a91…`): turn 1 opening, 11 open.
- Turn 2 (PO clarifications + explicit "add this as a new issue with a
  short title and description" ask): facilitator resolved B-1/B-4/E-2/
  E-4/E-5/E-8, minted **F-1 "Fallback for PSP service degradation"**
  with a full same-turn IssueDraft, re-synthesis produced E-9. Turn
  record carries the `new_issues` draft (verified server-side).
- Acceptance with open issues → synchronous finalize → completed, 2
  report formats, downloaded over signed fake-gcs HTTPS.
- Report verified: **Issues section present** (16 entries, every id
  titled + described + severity/source; F-1 marked "raised by
  facilitator"); **every Resolutions row titled** (B-1 — Epic
  Misalignment — resolved (turn 2): …); **every Remaining-open row
  titled** incl. F-1; **no bare ids anywhere**. The resolved-and-dropped
  six (B-1/B-4/E-2/E-4/E-5/E-8) kept their v1 descriptors via the union
  fix — the exact failure case of finding 2.
- Compose Postgres now: story-02, story-09, **story-05 completed**;
  story-01/-04/-06 (+ story-03, abandoned mid-gate with a wedged turn-2
  after the pre-fix failures) active.

Verification: agent-kit **104**, facilitator-adapter **3+1s**,
orchestration **96+11s**, stack recomposed (`make agents-compose-up`)
twice; other suites unchanged from session 43 baseline.

## Item F + webui debt fixes (session 45, 2026-09-16) — D20

Owner decision D20 (chat, this session): Item F via option (a) —
server-persisted `processing_stage` marker + polling of the existing
read endpoints; the three §D19 webui debt items fixed in the same pass.
Design detail in `docs-local/local-decisions.md` D20.

### What was implemented

- **Contract** (review-schemas 0.6.0 → 0.7.0): `ProcessingStage` literal +
  `SessionSummary.processing_stage` (inherited by `SessionDetail`);
  `docs/design/schemas.md` (API section + durable-records note: the column
  is live view state, not part of `SessionRecord`) and
  `docs/design/api-contract.md` (progress paragraph under GET /sessions,
  incl. flow-1 discovery via the story-filtered list). Migration
  `0003_processing_stage.sql` (nullable, check-constrained column).
- **Orchestration**: `records_store.set_processing_stage` /
  `get_processing_stage`; `list_sessions` returns (record, stage) pairs.
  Flow 1 publishes reviewing → synthesizing → facilitator (extracted
  `_initial_pipeline`; wrapper clears the stage on any failure). Flow 2
  publishes facilitator → delegating → synthesizing → finalizing (before
  each step; the finalize-retry endpoint too); `run_turn`'s finally clears
  the stage under the lease — the marker never outlives the lease holder.
  `GET /sessions` list + `GET /sessions/{id}` detail expose the stage.
- **Webui** (`static/progress.js` new): `stageText` labels + a
  `pollProcessingStage` loop (first read immediate, stops itself when the
  stage clears). `messages.js` gains an ephemeral `.message-progress`
  placeholder bubble (never persisted, never in history replay).
  `chat.js`: every in-flight turn shows the placeholder updated by
  polling, removed and replaced by the real reply; opening a session
  clears stale status banners; a passive read-only mode renders the
  placeholder when the server reports a processing session (e.g. creation
  still running); mid-turn reload resumes by re-issuing the persisted
  body with the persisted idempotency key (canonical replay). `api.js`:
  `pending:turn:{id}:body` persisted next to the key; `getPendingTurn` /
  `clearPendingTurn`; `fetchSessions`. `app.js`: the creation spinner
  polls the story-filtered session list and opens the session view early
  (passive mode) once the processing session appears.

### Debt items — status

1. Optimistic bubble after a failed turn: **fixed** (removed; message
   restored to the composer for editing).
2. Stale error banner across session switch: **fixed** (openSession
   clears the status line; leave flow tested).
3. Refresh mid-turn: **fixed** (pending body + key replay on boot;
   composer locked while resuming).

### Verification (deterministic tier)

- review-schemas **171** (+1 stage field), orchestration **100 +11s**
  (+4: flow-1 stage progression + clear, failed-creation clear, turn
  stage progression, finalize-stage visibility during flow 3),
  agent-kit **104**, mcp-report **36**, webui **pytest 11 + vitest 54**
  (+10: pending-body persistence/clear, getPendingTurn/clearPendingTurn,
  fetchSessions, SESSION_LOCKED same-key retry, failed-turn bubble
  restore, stale-banner clear, pending resume, live stage placeholders,
  passive-view completion + leave-stops-poll).
- Live gate (browser walkthrough with visible stage placeholders) folds
  into the increment-4 exit walkthrough — pending.

### Gotchas / notes

- The stage is advisory; if a process crashes mid-flow the marker can go
  stale (non-null at rest). The UI only shows it while its own POST is
  outstanding or a passive read observes it, and the lease-scoped finally
  clears it on every normal failure path. A crashed holder's stale marker
  disappears at the latest when the takeover/finalize path completes.
- Pre-D20 pending keys (key without body) cannot be re-issued; chat clears
  them on next open (no canonical replay possible — the turn outcome, if
  any, is in history replay).
- jsdom test gotcha: `vi.clearAllMocks()` does not reset
  `mockReturnValue` implementations — leaked the resume test's
  `getPendingTurn` into the placeholder test (deadlock via openSession's
  awaited resume). beforeEach now uses `vi.resetAllMocks()`.

### Independent review (session 45) + fixes

Read-only subagent review of the full diff: verdict **Needs fixes** —
1 Important + 4 minors; all fixed in-session:

1. **Important — passive-mode `inFlight` leak**: `openSession`'s passive
   branch set `inFlight = true` but nothing reset it (the `onDone`
   re-open re-entered with the flag still set) — the composer stayed
   permanently disabled after any passive view (exactly the flow-1
   progress headline). Fix: `openSession` resets the flag at open and
   `onDone` clears + re-syncs before the history re-render; two new
   tests (passive → done → composer enabled; leave stops the poll).
2. SESSION_LOCKED resume gap: the api client now retries 409
   SESSION_LOCKED with the SAME key (contract: retryable), waiting for
   the envelope's `retry_after_seconds` — the common reload case
   (original request still holding the lease) converges to the canonical
   replay instead of surfacing an error and dropping the pending body.
   New test; the non-retryable-409 truth table dropped its
   SESSION_LOCKED row (behavior changed intentionally).
3. Passive poll not stopped on "choose another story" — the leave
   handler now stops it (tested).
4. Minor style (records_store stray blank line) + defensive removal of a
   stale `${scope}:body` when a caller passes no pendingBody.

Post-fix verification: webui **pytest 11 + vitest 54**; orchestration /
review-schemas / agent-kit / mcp-report re-run green (counts below).

### Live-testing findings (owner browser session, story-15) + fixes

First live exercise of the D20 progress UI surfaced two client bugs,
both fixed in-session:

1. **Leading-null poll race (Item F)**: the placeholder stayed at the
   generic "processing…" text for a whole delegated turn. Root cause:
   `pollProcessingStage`'s immediate first read fires before the server
   writes its first stage (lease → claim → input assembly precede it);
   the null observation was treated as "flow finished" and the loop
   stopped itself. Fix: a null stage only ends the loop after a stage
   was observed (or after a bounded run of 3 never-stage nulls — covers
   a flow finishing between the arming read and the first poll). New
   `tests/frontend/progress.test.js` (3 tests) — deterministic tests
   missed the race because staged mocks always answered instantly.
2. **Stale report links**: opening an active session did not clear
   `#report-links`, so links rendered by a previously completed session
   (the boot resumed story-09's completed view) survived the switch and
   pointed at expired (15-min TTL) URLs. Fix: `openSession` always
   re-renders the container (empty unless completed). Test added.

**Gotcha — fake-gcs memory backend**: `docker compose up --build`
recreates containers; fake-gcs runs `-backend memory` with no volume, so
**every stack rebuild wipes all stored artifacts** — report downloads of
previously completed sessions 404 afterwards (their signed URLs point at
vanished objects). Expected for the local substitute; noted so a 404
after a rebuild is not misread as a report-server defect. The compose
Postgres is volume-backed and survives rebuilds — which is also why new
migrations must be applied to it manually (0003 was applied in-container
mirroring run-migrations.sh: transaction + schema_migrations insert);
`agents-compose-up` does not run migrations.

Verification after the fixes: webui **pytest 11 + vitest 59**.

**Follow-up (same live session)**: turn-3 "facilitator only" stage was
*correct* (invoke=none — no delegation that turn); turn-4 showed the full
facilitator → delegating → synthesizing sequence. The reappearing stale
report link was the browser serving a heuristically cached pre-fix
`chat.js` (StaticFiles sent no Cache-Control). Fix: webui static
responses now carry `Cache-Control: no-cache` (middleware; ETag
revalidation still avoids re-downloads) — webui **pytest 12**, vitest 59.

### Live D20 verification (owner browser, story-15, same session)

Turn-by-turn: turn 1 opening (creation progress verified earlier);
turn 2 delegated (pre-fix JS, stages not shown); turn 3 facilitator-only
("facilitator is drafting…" correctly the sole stage — invoke=none);
turn 4 delegated — full sequence **facilitator → reviewers re-checking →
synthesis merging** shown after the leading-null fix. Report-links bugs
fixed (stale links cleared; no-cache static headers). Remaining live
checks fold into increment 4: park, mid-turn refresh resume, finalize
stage, regenerate links. UX gap found (first facilitator reply precedes
the re-review it requests; outcome surfaces only in the next turn or the
report) → recorded as future-extensions **Item G** (flow-2 two-call
design change; owner's shape: facilitator → reviewers → synthesis →
facilitator → PO, first reply hidden, second repeats key findings).

## Item G implementation — post-delegation summary turn (2026-09-17, session 47)

Docs (D21) were applied session 46; this session implemented them. No
cloud actions; Cloud SQL STOPPED; local compose stack up throughout
(orchestration :8130, webui :8120).

### What was implemented

- **review-schemas 0.7.0 → 0.8.0**: `delegation_rationale_reply: Text |
  None` on `TurnResponse`, `TurnView`, `CanonicalTurnResult` (api.py) and
  `TurnRecord` (records.py); package-install test bumped with the version.
- **Migration 0004** (`0004_turn_delegation_rationale.sql`): nullable
  `turns.delegation_rationale_reply` — applied to the compose Postgres
  (in-container run-migrations.sh, mirroring 0003).
- **Orchestration flow 2** (`turns_flow.py`, `turn_execution.py`,
  `flows.py`, `records_store.py`, `sessions_api.py`):
  - when a turn produced a synthesis (delegation ran reviewers or
    `reuse_previous`), the facilitator is invoked a **second time** in the
    same turn (`_invoke_summary_facilitator`): distinct invocation id
    `facilitator_summary_invocation_id` (uuid5 salt
    `facilitator-summary:{turn}`) → own reconciliation result + corrective
    budget; fresh synthesis report passed from `maybe_synthesize` (new
    `SynthesisOutcome(reference, report, produced)`); evidence references
    re-listed from the run lineage **after** the re-review saves;
    decision state = prior turns **merged with the first output**
    (latest-wins resolutions via `latest_resolutions`, open list from the
    pre-delegation delegation).
  - the second output is final/gate-authoritative: reply, delegation,
    stamped resolutions, `new_issues`; the first reply persists as
    `delegation_rationale_reply` (TurnRecord, TurnResponse, canonical
    idempotent replay, SessionDetail TurnView). Any delegation the summary
    call emits is stored but never executed this turn (next PO turn).
  - **gate**: `evaluate_gate` drops the old
    `synthesis_produced ⇒ continue` rule — a delegated turn finalizes
    same-turn when the final output has empty `open_issues` + `invoke=none`;
    park-at-10 precedence unchanged (the summary call still runs, then
    parks). One facilitator-turn count per turn despite two invocations
    (opening-turn flow unchanged).
  - audit: two `agent_runs` rows per delegated turn
    (`facilitator:{turn}` + `facilitator-summary:{turn}` run-id labels;
    `record_run` gained a `run_label` override).
- **Prompt** (`prompts/facilitator.md`): new "Post-delegation summary
  turn" section — pre-delegation reply invisible to the PO (repeat
  important findings), output authoritative, no same-turn delegation
  chaining.
- **Webui: intentionally unchanged** — it renders only
  `facilitator_reply`, which is now always the final (summary) reply;
  option (a) needs no client change.

### Verification (deterministic tier)

review-schemas **173** (+2), orchestration **105+11s** (+5: same-turn
finalize, merged decision state, no-chaining, detail exposure, delegated
replay), agent-kit **104**, facilitator adapter **3+1s**, webui **12 +
vitest 59**, compose contract **20**.

### Independent review (session 47)

Read-only subagent review: **Ready to proceed**, no Critical/Important.
Minors: (1) dead `story` parameter on `_invoke_summary_facilitator` —
**fixed in-session** (re-ran orchestration 105+11s); (2) worst-case
two-call attempt budget (2×120 s × 2 attempts) can exceed the 300 s
end-to-end deadline — design-conformant (deadline retained per D21) but
delegated turns are likelier to hit DeadlineExceeded; per-attempt
clamping holds; recovery = same-key retry + per-invocation
reconciliation — **watch at the live gate**; (3) the gate could finalize
away a summary-call `reuse_previous=true` contradiction (empty
open_issues + invoke=none) — literal-gate-conformant, prompt steers
against it; accepted edge case recorded here. Coverage gaps noted: no
deterministic test for a crash between the two invocations (ids are
deterministic functions of the key, so takeover replays both stored
results); no test for minor 3.

### Remaining (live tier)

Live gate on a delegated turn (fresh session; watch the 5-min deadline
over two facilitator calls + reviewers + synthesis) folds into the
increment-4 walkthrough or runs before it; orchestration + webui images
must be rebuilt first (compose stack still carries pre-0004 code).

## Item G live gate — post-delegation summary turn (session 48, 2026-09-12; **PASS**)

Owner-driven from the browser (webui :8120), fresh session
`sess-f5e115d5-e445…` on **story-07** ("30-minute order edit window after
purchase"; free-story check first — active slots were story-01/-03/-04/-06/
-14/-15). Stack rebuilt first (`make agents-compose-up`, all services
recreated; `delegation_rationale_reply` confirmed present in the running
orchestration image; migration 0004 already applied to the volume-backed
compose Postgres — no re-run needed).

### Gate evidence (turn 2, delegated; correlation `8af05e6e…`)

- PO message answered the turn-1 clarifications and explicitly requested a
  focused reviewer analysis of payment partial-charges/refunds — delegation
  trigger.
- **PO view**: chat shows only the final summary reply ("The re-review has
  been completed…") — self-contained, repeats the important findings (D21
  prompt rule); the pre-delegation reply does **not** appear.
- **Turn record** (SessionDetail): `delegation_rationale_reply` persisted
  (1824 chars, "Thank you for the clarifications… C-1, which is now
  resolved…"); `facilitator_reply` = the summary the PO saw; second-call
  `delegation.invoke = "none"` (no same-turn chaining); one turn count
  (2/10) despite two facilitator invocations.
- **agent_runs (turn 2)**: facilitator (first call, delegation decision)
  → business-reviewer v2 + engineering-reviewer v2 (parallel) → synthesis
  v2 → facilitator (second call, summary). All succeeded.
- **D19 behavior intact**: new issues B-6–B-9 minted with same-turn
  descriptors; E-3/E-4/E-6/E-11 resolved with superseded-by explanations.
- **Timing**: first facilitator call → second facilitator call ≈ **78 s**
  visible span — well inside the 300 s deadline. The session-47 review
  risk (two-call worst case vs deadline) did not materialize.
- Observed behavior, no action: `corrective_reprompts = 1` on both
  facilitator calls (validation loop engaged once each, succeeded).

### Webui findings from this walkthrough (owner-reported; to address)

1. **"Choose another story" needs a confirmation dialog** — currently a
   single miss-click leaves the session (client-side leave only).
2. **Story picker needs an open/active sessions list with resume**, and/or
   the ability to open a new session for a story that already has an
   active one. Today selecting such a story yields only the 409
   `STORY_SESSION_ACTIVE` error ("this story already has an active
   session — finish it before starting a new one") with **no way back into
   that session from the picker**. Note the server side is correct
   (one-active-per-story); this is a client UX gap. Cross-check the
   pre-D19 active sessions (story-01/-04/-06) caveat from the Item E gate
   — those may be un-finalizable; a resume path must not deadlock the
   story (consider park + restart affordance from the parked view).
3. **Bug**: after leaving an active session via "choose another story",
   the "start review session" button stays disabled until a page reload.
   Probably stale client state / listener wiring on re-entering the
   picker; likely an easy fix.

## Increment 4 webui fixes — open-session resume, leave confirmation, picker button (session 48, 2026-09-12)

Owner-reported findings from the Item G gate walkthrough (§ above), fixed
in-session, test-first (5 new sessions-list vitest + 1 chat confirm test).

- **Leave confirmation**: "choose another story" now always confirms
  ("Leave this session? It stays active and can be resumed from the story
  picker."); the in-flight variant ("A turn is still processing — leave
  anyway?") is kept. Prevents miss-clicks (finding 1).
- **Open-sessions list**: new `webui/static/sessions-list.js` renders the
  active sessions (story title, processing-stage annotation when mid-turn)
  with a resume button in a new `#open-sessions` block above the story
  list; `app.js showPicker` fetches `GET /sessions` in parallel with the
  stories and `resumeSession` stores the id + opens the chat view. The 409
  `STORY_SESSION_ACTIVE` hint now points at the list instead of dead-ending
  (finding 2). Starting a *new* session on a story with an active one
  stays blocked server-side (one-active-per-story, by design) — the
  fresh-start path is resume → park → "start a new session on this story".
- **Picker button bug**: `startSession` disables the confirm button and only
  the error path re-enables it, so returning from a created session left it
  disabled until reload; `showPicker` now resets it (finding 3, one line,
  root cause recorded).

Verification: webui pytest **12** + vitest **65** (+6); webui image
rebuilt + redeployed; owner verified live in the browser (confirm dialog,
open-sessions list with resume, button re-enabled, 409 hint). No
orchestration/server changes; independent review skipped (small
client-side, test-covered, owner-verified — recorded here).

Remaining increment-4 walkthrough items on the story-07 session
(`sess-f5e115d5-e445…`, 2/10 turns): mid-turn refresh resume, live park,
accept → finalize → fresh report links + regenerate.

## Increment 4 walkthrough — exit gate items (session 49, 2026-09-12; **PASS with one deferred finding**)

Local Docker stack up throughout, no cloud actions, Cloud SQL STOPPED.

### Walkthrough evidence (owner-driven, browser)

- **Session restart after completion (bug found + fixed)**: after
  completing story-07 (session 48's `sess-f5e115d5…`), creating a new
  session on the same story returned **409 `STORY_SESSION_ACTIVE`**
  although the session was `completed`. Root cause (orchestration): the
  `one_active_run_per_story` partial index excludes `completed`/`parked`
  **run** states, but nothing ever transitioned `story_runs` — park
  (`turns_flow._persist_and_respond`) and finalize
  (`finalization.complete_session`) updated only the `sessions` row. All
  10 compose runs sat at `active` (four with completed sessions). Fix:
  `records_store.update_session` transitions the session's story run to
  the same terminal state on the same connection (joins the caller's
  transaction) — single chokepoint, rows can never diverge. Tests written
  first (red confirmed): `test_park_at_facilitator_turn_10` extended,
  `test_completed_session_releases_story_for_new_run` new. Orchestration
  **106 +11s**; image rebuilt; 4 stale compose rows backfilled to
  `completed`; live check: new story-07 session 201 through the webui
  proxy.
- **Delegated dialogue arcs**: turns 2–4 on `sess-230a5104…` (fresh
  story-07 session) — business clarifications → delegated re-review with
  minted conflicts C-1/C-2 → re-engaged business reviewer, B-1…B-5 +
  E-1…E-6/E-10/E-12 resolved. D19/D18 behavior intact in the live UI
  (titled issues, resolved-by-clarification dispositions).
- **Mid-turn refresh**: turn carried through reload via persisted
  body + idempotency key (canonical replay); stage placeholder visible in
  the passive view. **Deferred finding**: the pending PO bubble is not
  rendered in the passive view in the owner's browser. Fixed test-first
  (`postWithIdempotentKey` keeps key+body on budget-exhausted
  `SESSION_LOCKED`; `openSession` passive branch renders the pending PO
  bubble when the logical request holds the lease) — vitest 65→67, but
  the owner still observed the old behavior live (suspected browser
  caching; server verified serving the new JS byte-level). Owner
  decision: minor debt, not MVP-blocking (D22-4).
- **Accept → finalize → report** (story-07, `sess-230a5104…`, turn 5):
  accept-with-open-issues → synchronous finalize → completed view → both
  report formats downloaded over signed fake-gcs HTTPS → reload
  persisted → **regenerate produced fresh signed URLs** (X-Goog-Date
  08:37→08:39, distinct signatures). Owner-verified.
- **Live park** (story-13, `sess-74778481…`): driven to turn 10 with
  short PO turns → **park fired**; session **and** story run both
  `parked` (run-release fix verified live on the park path).
- **Restart-on-same-story** (from the parked view): new story-13 session
  created (`sess-61c863b2…`, turn 1/10 active) — no 409; parked session
  remains readable.

### New owner decisions → D22 (docs applied this session)

- **Abandon/close session** (`POST /sessions/{id}/abandon`, explicit
  park-now for stuck active/finalizing sessions) — docs applied
  (api-contract, schemas `AbandonSessionResponse`, architecture);
  implementation + review scheduled for the next session.
- **Historical sessions view** (webui-only past-sessions list) —
  scheduled with the abandon implementation.
- Parallel active sessions per story: considered and **rejected** (not
  even a future extension).
- Legacy stuck compose sessions (story-01/-03/-04/-06/-14/-15,
  pre-rebuild, artifacts wiped from fake-gcs memory backend): to be
  closed via the abandon endpoint once implemented (their "missing
  synthesis artifact in the session lineage" errors are the rebuild-wipe
  symptom).

### Verification (session 49)

- orchestration **106 +11s** (+1 story-run release), webui **pytest 12 +
  vitest 67** (+2 pending-bubble passive view), both images rebuilt +
  redeployed; orchestration live checks 201/200 through the webui proxy.
- Remaining for Phase 7 close: D22 implementation (abandon + history
  view), then full regression suites, independent phase review,
  development-plan COMPLETE, completion review.

## Session 50 (2026-09-20) — D22 implementation + Phase 7 close

Local Docker stack up throughout (orchestration + webui images rebuilt twice
this session), no cloud actions, Cloud SQL STOPPED.

### D22 implementation (test-first, per api-contract.md state table)

- **review-schemas 0.8.0 → 0.9.0**: `AbandonSessionResponse` in
  `api.py`, exported via `__init__`/`__all__`/install-test EXPECTED_EXPORTS
  (the export was the phase-review Important — both package and test omitted
  it, so the equality test could not catch it; fixed in-session).
- **Orchestration** `abandon_api.py`: `POST /sessions/{id}/abandon` — key-v4
  422, unknown 404, lease acquire (`SESSION_LOCKED` retryable w/
  retry_after), claim under the lease (REPLAY returns the stored canonical;
  IN_PROGRESS proceeds — we own the lease), re-read state (active/finalizing
  → park; terminal → `SESSION_READ_ONLY` + fresh-claim release), atomic
  transaction `update_session(state=parked)` + `idempotency.complete`
  (story run parks in the same statement batch; count unchanged), stage
  cleared + lease released in `finally`. Route
  `POST /api/v1/sessions/{}/abandon`.
- **Drive-by bug fix** in `records_store.update_session`: the no-`conn`
  branch passed `None` (not the borrowed connection) to
  `_retire_story_run` — a latent crash on any future pool-path terminal
  transition; one word (`borrowed`), caught while implementing abandon.
- **Webui**: `abandonSession` in `api.js` (empty body + key scope
  `pending:abandon:{id}`, 503/SESSION_LOCKED same-key retry,
  budget-exhausted SESSION_LOCKED keeps the key — same core as
  finalizeRetry); abandon button (confirm dialog) on the active and
  finalizing views in `chat.js`, success → parked read-only view;
  SESSION_LOCKED hint reworded to "session lease" (review minor);
  `renderPastSessions` in `sessions-list.js` wired into the picker
  (`#past-sessions` block in `index.html`) — parked/completed sessions,
  multiple per story, read-only open via the existing session view.
- **Tests**: review-schemas +3 (model rules); orchestration +10 in
  `tests/test_abandon.py` (full state table, story release incl. new
  201-on-same-story, same-key replay, lease contention, stale-claim release
  on read-only, non-v4 key, stage clearing); webui +9 vitest
  (abandonSession idempotency/retry/read-only, abandon button
  active/finalizing/absent-on-terminal/error path, past-sessions render).

### Live: six legacy stuck sessions abandoned

Through orchestration :8130 directly (keys uuidgen): story-01/-03/-04/-06/-14
active sessions → `200 {"state":"parked"}`; their story runs verified `parked`
in the compose Postgres (stories released). story-15's session turned out
already `completed` — the abandon returned `409 SESSION_READ_ONLY`
(non-retryable) exactly per the state table: live evidence of the terminal
branch. Remaining compose sessions: story-13 active (second session, turn
history intact) + parked/completed history.

### Phase 7 close

- **Regressions** (all at/above baseline): review-schemas **176** (+3),
  ado-wire 7, dataset 36, mcp-ingress 7, mcp-story 67, mcp-artifact 32,
  mcp-report 36, compose contract 20, agent-kit 104, agents 4×4,
  adapters 6+2s / 7+1s / 7+2s / 3+1s, orchestration **116 +11s** (+10),
  webui **12 + vitest 76** (+9).
- **Independent phase review** (read-only subagent, snapshot
  `b8a1416..HEAD` + working tree): verdict **Ready to proceed** with
  1 Important (`AbandonSessionResponse` missing from the public
  exports) + 2 minors (stale-claim-release test, SESSION_LOCKED hint
  wording) — all three fixed in-session; suites re-run green
  (review-schemas 176, orchestration 116+11s, webui 12+76).
- Phase 7 marked COMPLETE in development-plan.md.
- Commits: `1b0f2ad` (feat, D22 code + tests) + this runbook/handoff commit.

### Gotchas

- The review-schemas export-equality test can never catch a name missing
  from *both* `__all__` and EXPECTED_EXPORTS — new public models must be
  added consciously in three places (api.py, `__init__` import + `__all__`,
  EXPECTED_EXPORTS) and cross-checked against schemas.md.

## Post-Phase-7 UI/UX follow-up (2026-09-12)

Owner approved the local rebuild after the UI/UX fixes. No cloud actions;
Cloud SQL remains STOPPED. The compose Postgres container is persistent and
was left running.

Commands run:

    make webui-test            # pytest 12 + vitest 77 passed
    make orchestration-test    # 117 passed, 11 skipped
    make agents-compose-up     # rebuilt compose images and recreated services
    curl --fail http://127.0.0.1:8120/health
    # {"status":"ok"}
    curl --fail http://127.0.0.1:8120/api/v1/stories/story-43
    # 200; "VAT breakdown table in the order confirmation email", 3 comments

Delivered: picker session actions use left-aligned controls; header reports
"FastAPI backend" reachability; story preview normalizes plain-text lines to
sanitized Markdown paragraphs; session action controls sit beneath the
composer; and orchestration validates story-MCP JSON through the JSON boundary
so comment `created_at` timestamps no longer cause invalid-payload 503s.

Gotcha: the first `make orchestration-test` attempt hit the known throwaway
Postgres startup race (`database system is starting up`) before tests began;
the unchanged target passed on its next run.

## Mobile picker fix — floating confirm button (2026-09-16, dev server; owner-approved "please run it")

Owner-reported defect carried in the HANDOFF: on phones the story list sits
below the fold (open/past session lists above it) while the confirm button is
at the top, forcing a scroll-down-then-up dance. Owner chose the minimal fix
(floating button only; no list reorder).

Change: `webui/static/app.css` mobile media query (`max-width: 36rem`) only —
`#confirm-story` becomes `position: fixed` bottom-right with a shadow;
`#picker-view` gains bottom padding so the button never covers content. No
HTML/JS changes, so no new test applies (jsdom cannot assert visual position;
all behavior unchanged and covered).

Commands run:

    make webui-test   # pytest 25 + vitest 89 passed
    git diff --check  # clean
    git add webui/static/app.css
    git commit -m "fix: float story confirm button on mobile pickers"   # 05592e8
    bash deploy/cloud-run/webui/deploy.sh
    curl -o /dev/null -w "%{http_code}\n" https://story-review.mmz.sh/health
    # 200
    curl https://story-review.mmz.sh/app.css | tail   # new fixed-position rules served live

Deploy evidence: image `20260916-0511-05592e8` (tag maps to commit
`05592e8`), Cloud Run revision `webui-00003-bhv`, 100% traffic, public
domain healthy with the new CSS. Local compose stack still serves the
previous baked image (`make agents-compose-up` needed to preview there).
Owner pushes main.
