# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D15),
`docs-local/development-plan.md` (phase scope/exit criteria), and git history
(the record of what changed). Do not let this file grow back into an archive.

Last updated: 2026-09-12 (session 48 — **Item G live gate PASS** on story-07;
three owner-reported webui findings fixed: open-session resume list, leave
confirmation, picker button bug; owner-verified live. Prior: session 47 —
D21/Item G implemented.)

## Where we are

- **Phase 6 — Orchestration (FastAPI): COMPLETE and CLOSED**
  (sessions 32–38; detail in Runbook 12, decisions D15 + amendments
  1–3). All gates green; live integration suite PASS (3 passed in 367 s).
- **Phase 7 (Web UI) in progress** — increments 0–3 COMPLETE (sessions
  40–42, Runbook 13 + D17 amendment 1). Item E (D18) and D19 done with
  live gates PASS (sessions 43–44). **Session 45: D20 — Item F live
  processing-stage progress (option a) + all three webui debt items
  fixed** (Runbook 13 §Item F; uncommitted). **Session 48: Item G live
gate PASS + three webui UX fixes**. Remaining: increment 4
  (exit gate — example-interaction walkthrough end-to-end + close;
walkthrough should exercise the new stage placeholders). Compose
  Postgres sessions: story-02 + story-09 + story-05 completed,
  story-01/-03/-04/-06/-14/-15 + story-07 (2/10, the Item G gate session)
  active.
- **Phase 5 COMPLETE and CLOSED** (session 31): all increments green, exit
  gate PASS (session 30), completion review Ready-to-close. Detail: Runbook
  11, D13 + amendments, D14 + amendment 1.
- **Phase 4 COMPLETE and CLOSED** (session 26). Detail: Runbook 10, D10 +
  amendments, D11/D12.
- **Phase 3 COMPLETE** (session 16): 45 stories (42 core + 3 t1-only comment
  scenarios), 10 expected files. Detail: Runbooks 08–09.
- **Phase 2 COMPLETE and post-reviewed** (session 11). Detail: Runbook 07.
- **Phase 1 complete**: e2e trace under the D8 ingress fallback; spike torn
  down (Runbook 06).
- Docs design frozen on `docs/initial-frozen` (`d5cb413`); home-phase docs in
  `docs-local/`. Remote `origin` = private GitLab
  (`mmz-personal/capstone-project`); **owner pushes** (main +
  `docs/initial-frozen`).

## Previous Session Summary
Session 48 (2026-09-12, main PC — **Item G live gate + increment-4 webui
fixes**; local Docker stack rebuilt and up throughout, no cloud actions,
Cloud SQL STOPPED):
- **Stack rebuilt** (`make agents-compose-up`): orchestration now carries
  the D21/0004 code (`delegation_rationale_reply` confirmed in the running
  image); migration 0004 already applied to the volume-backed compose
  Postgres.
- **Item G live gate PASS** (owner-driven, story-07, fresh session
  `sess-f5e115d5-e445…`): delegated turn 2 — PO saw only the summary
  reply; `delegation_rationale_reply` persisted (1824 chars); no same-turn
  delegation chaining; one turn count despite two facilitator invocations;
  B-6–B-9 minted with descriptors (D19 intact); two-call arc ≈ 78 s — well
  inside the 300 s deadline (the session-47 review risk did not
  materialize). Observed: `corrective_reprompts = 1` on both facilitator
  calls (succeeded; recorded, no action). Evidence in Runbook 13 §Item G
  live gate.
- **Three webui findings fixed** (owner-reported at the gate, test-first,
  owner-verified live): (1) "choose another story" always confirms;
  (2) open-sessions list in the picker with resume buttons + 409 hint
  pointing at it (new `sessions-list.js`; new-session-per-active-story
  stays blocked by design — fresh start = resume → park → restart);
  (3) picker confirm-button re-enabled on `showPicker` (root cause:
  success path never re-enabled it).
- Verification: webui pytest **12 + vitest 65** (+6); no server changes;
independent review skipped (small client-side, test-covered,
  owner-verified — recorded in the runbook).

Session 47 (2026-09-17, main PC — **Item G (D21) implementation**; local
Docker stack up, no cloud actions, Cloud SQL STOPPED):
- **review-schemas 0.7.0 → 0.8.0**: `delegation_rationale_reply` on
  TurnResponse/TurnView/TurnRecord/CanonicalTurnResult (+2 tests, install
test bumped).
- **Orchestration flow 2**: when a turn produced a synthesis, a second
  facilitator invocation runs in-turn (`facilitator_summary_invocation_id`,
  own reconciliation/budget; fresh synthesis + lineage-fresh evidence;
  decision state merged prior + first output); second output final and
gate-authoritative; first reply persisted as rationale; old
  "synthesis ⇒ continue" gate rule removed (same-turn finalize possible);
park-at-10 unchanged; one turn count despite two invocations; two
agent_runs rows (`facilitator-summary:{turn}` label). Migration **0004**
applied to the compose Postgres. Prompt: summary-turn rules added.
**Webui unchanged** (renders only final reply — option a).
- **Review**: read-only subagent **Ready to proceed**; minor fix
  (dead param) done in-session; recorded risks: two-call worst case vs
  5-min deadline (watch at live gate), gate-finalized
  `reuse_previous` edge case (Runbook 13 §Item G).
- Verification: review-schemas **173**, orchestration **105+11s**,
  agent-kit **104**, facilitator adapter **3+1s**, webui **12 + vitest
  59**, compose contract **20**. Commits: `ba9d464` (feat) + `b303525`
  (runbook/handoff) — amended for the commit references.

Session 46 (2026-09-17, main PC — **Item G design (D21), docs-only**; no
cloud actions, Cloud SQL STOPPED, no suites run — documentation only):
- **Blocker check clean**: D20 docs commit + frozen cherry-pick already done,
tree clean; Phase 7 increment 4 independent.
- **Owner decision D21** (chat, resolving Item G's open questions):
presentation **option (a)** — chat shows only the final (second-call) reply;
pre-delegation reply persisted as new `delegation_rationale_reply` field
(TurnResponse/TurnView/TurnRecord/CanonicalTurnResult); **prompt rule** that
the pre-delegation reply is invisible to the PO (second reply must repeat
important findings); **gate precedence on the final typed output** — old
"synthesis ⇒ continue" rule removed, delegated turns can finalize same-turn;
**one facilitator-turn count despite two invocations** (distinct invocation
ids, reconciliation + corrective re-prompt budget each); second call cannot
chain a delegation within the same turn; extra model-call cost accepted.
- **Docs applied**: `docs/design/data-flow.md` §2 (prose, mermaid, gate
precedence, ASCII regenerated from `flow2.puml`), `agents.md`,
`api-contract.md` (TurnResponse + flow-2 stage sequence now `facilitator →
delegating → synthesizing → facilitator → finalizing`), `schemas.md`,
`architecture.md`, `observability.md`, `example-interaction.md`; D21 recorded
in local-decisions; future-extensions Item G → design-decided status.
- **Commits**: `e64c34b` (docs, atomic) + `a5a195b` (docs-local) on main;
`e64c34b` cherry-picked to `docs/initial-frozen` as `5e0de47` (clean).
Owner to push both branches. Intermediate `flow2.atxt` in `trash/`.
- **Risk noted for implementation**: the 5-min turn deadline now covers two
facilitator calls + reviewers + synthesis; per-attempt clamping should hold,
watch at the live gate.

Session 45 (2026-09-17, main PC — **D20: Item F live progress + webui
debt fixes**; local Docker, Cloud SQL STOPPED, no cloud actions):
- **Owner decision D20**: Item F via option (a) — orchestration
  persists an advisory nullable `processing_stage` on sessions
  (migration 0003; NOT part of SessionRecord — live view state),
  exposed on SessionSummary/SessionDetail (review-schemas 0.6.0 →
  0.7.0); UI polls GET /sessions(/{id}) while its synchronous POST is
  outstanding. Docs updated (schemas.md, api-contract.md) — atomic
  docs commit + frozen cherry-pick **due**.
- **Orchestration**: stage publication in flows 1/2/3 + finalize retry
  (`reviewing`/`synthesizing`/`facilitator`/`delegating`/
  `finalizing`), cleared on completion/failure (lease-scoped finally,
  flow-1 except wrapper); list returns (record, stage) pairs; detail
  exposes the stage.
- **Webui**: new `progress.js` (labels + poll loop); ephemeral
  `.message-progress` placeholder bubbles replaced by the real reply;
  picker polls the list to discover the processing session (one-active-
  per-story) and opens the session view early in a passive read-only
  mode; **debt fixes**: failed turn removes the optimistic bubble and
  restores the text; stale banners cleared on open; mid-turn reload
  re-issues the persisted body with the persisted key (canonical
  replay); SESSION_LOCKED now retried same-key with
  retry_after_seconds.
- **Review**: independent read-only review → 1 Important (passive-mode
  inFlight leak) + minors, all fixed in-session; focused re-review
  **Ready to proceed**. jsdom gotcha recorded (clearAllMocks does not
  reset implementations).
- Verification: review-schemas **171**, orchestration **100+11s**,
  webui **11 + 54 vitest**, agent-kit **104**, mcp-report **36**.
  Live verification of the placeholders folds into increment 4.

Session 44 (2026-09-16, main PC — **D19 live gate**; local Docker stack
up throughout, no cloud actions, Cloud SQL STOPPED):
- Goal: D19 live evidence. First attempts failed repeatably (story-03,
  then story-05): facilitator minted F-1 in prose but never emitted
  `new_issues`; corrective re-prompts produced byte-identical replies
  (md5-verified via the ADK `events` table in the facilitator DB — the
  fastest diagnosis path). Transient host-network outage to Google OAuth
  mid-gate was identified and excluded as cause.
- **Root cause 1 (Critical)**: `ServingSafeFacilitatorTurnOutput`
  (ADK `output_schema`) predates D19 — no `new_issues`, so Vertex
  structured output could never emit an IssueDraft. Fix:
  `MirrorIssueDraft` + field, test-first.
- **Root cause 2 (Important)**: catalog sourced from the latest
  synthesis only — first acceptance hit the completeness backstop
  (`FINAL_REVIEW_INVALID`, rolled back to active as designed) for the
  six turn-2-resolved ids the re-synthesis dropped. Owner decision:
  **catalog = union of all synthesis versions, latest wins** (docs
  updated + frozen cherry-pick); `run_flow3` fetches each turn's
  synthesis artifact.
- Supporting: facilitator prompt `new_issues` worked example;
  descriptor-validator rejection carries the inline JSON shape.
- **Gate PASS (story-05)**: F-1 minted with same-turn descriptor,
  accept-with-open-issues, report verified — Issues section (16 titled
  entries, F-1 "raised by facilitator"), all Resolutions/Remaining-open
  rows titled, no bare ids.
- Webui debt recorded (Runbook 13): optimistic bubble persists after
  failed turn; stale error banner survives session switch; refresh
  mid-turn drops pending message / may lose idempotency key.
- Verification: agent-kit **104**, orchestration **96+11s**,
  facilitator adapter **3+1s**; stack recomposed twice.

Session 43 (2026-09-16, main PC — Item E (D18) implementation + live gate;
local Docker stack up throughout, no cloud actions, Cloud SQL STOPPED):
- **Design + decisions**: `reopened` disposition + FinalizedReview
  consistency rule + `FINAL_REVIEW_INVALID` error code in
  `docs/design/schemas.md` (+ agents.md), frozen cherry-pick `7c8b9cf`;
  D18 + amendments 1–2 in local-decisions; phase-5 plan appendix records
  the `decision_state` request extension.
- **Code**: review_schemas 0.5.0 (`reopened`, shared `latest_resolutions`,
  backstop validator, new error code); agent_kit `DecisionState` on
  FacilitatorRequest + "Current decision state" renderer + lifecycle rule
  in `validate_turn_output` (prior-state reuse AND same-turn
  self-contradiction) via the corrective re-prompt loop; orchestration
  `_decision_state(turns)` assembly (None on opening turn), shared
  aggregation in finalization, backstop → 503 non-retryable → rollback to
  active; facilitator prompt lifecycle rules.
- **Review**: independent read-only review Ready-to-proceed; Important
  (same-turn self-contradiction gap) + minors fixed in-session (D18
  amendment 2).
- **Live gate PASS (owner-driven, story-09)**: resolve (10→6 open) →
  withdrawal → **reopened B-3/E-4, fresh ids E-7–E-9, no id reuse, no
  422** → accept with open issues → report: reopened issues in
  Resolutions, every remaining-open id never-resolved or reopened —
  consistent. Evidence in Runbook 13.
- **UI addition** (owner request): persistent "choose another story"
  control in every session state (client-side leave; in-flight confirm).
- **D19 (issue catalog) implemented after the gate** (owner: complete
  solution, no fallback debt; found at the D18 gate — reports showed bare
  ids): `IssueDraft` on `FacilitatorTurnOutput.new_issues` (minted ids
  must be described same-turn; adapter rule in validate_turn_output),
  `TurnRecord.new_issues` + migration 0002, `FinalizedReview.issues`
  (synthesis findings+conflicts ∪ facilitator drafts, synthesis wins,
  completeness validator → FINAL_REVIEW_INVALID), renderer "Issues"
  section + title annotations, prompt: open_issues = ids only.
  run_flow3 reordered (mark finalizing before the catalog fetch; fetch
  failures classified per the flow-3 table). Independent review
  (needs-fixes) findings fixed in-session: malformed synthesis content →
  non-retryable rollback; catalog overflow → clear error; catalog
  uniqueness + reuse-only-turn validators; fetch moved inside the
  failure-handling try. **Caveat recorded**: pre-D19 active sessions
  (story-01/-04/-06, prose open_issues) may now be un-finalizable by the
  completeness rule — expected; increment 4 should use a fresh session.
- Verification: review-schemas **170**, agent-kit **103**, orchestration
  **95+11s**, facilitator-adapter **3+1s**, mcp-report **36**, webui
  **pytest 11 + vitest 44**. Identifier check clean after the D18 commits.

Session 42 (2026-09-15, main PC — Phase 7 increments 2 + 3; local Docker
stack up throughout, no cloud actions, Cloud SQL STOPPED):
- **Increment 2 (chat view, dialogue turns, session resume)**:
  `api.js` gained `fetchSession`/`postTurn` with per-session pending
  idempotency keys (`pending:turn:{id}`, persisted before fetch, 503
  same-key retry, definitive 409/404/422; `po_accepted:true` carries no
  message) via a shared `postWithIdempotentKey` core; new `chat.js`
  session-view controller (history replay from SessionDetail, PO
  plain-text right / facilitator sanitized-markdown left + meta line,
  optimistic PO bubble, single in-flight turn, SESSION_LOCKED retry hint);
  `app.js` boot resumes `localStorage["session:id"]` (404 → clear →
  picker). Gate PASS on a substituted story: the owner's browser held a
  **story-02** session, not the planned story-04 — gated identically
  (3 dialogue turns, issues 10→7→4, synthesis v1→v3, reload-resume).
- **Increment 3 (park / acceptance / finalize / report download)**:
  `fetchReport`/`finalizeRetry` (key scope `pending:finalize:{id}`);
  rendering extracted to `messages.js`; accept-and-finalize control
  (confirm dialog), parked view with restart-on-same-story (picker
  preselect; listeners single-wired — double-wiring bug caught in
  implementation), finalizing retry control, completed view with report
  links + regeneration. Gate PASS: story-02 accepted from the browser →
  synchronous finalize → both report formats downloaded over signed
  fake-gcs HTTPS (`:9026`, cert warning accepted); reload persisted +
  regenerate produced fresh URLs. Park view jsdom-tested only — live
  park folds into the increment-4 walkthrough.
- **Design defect found at the gate → future-extensions Item E** (owner
  decision: address next session): turn-3 facilitator delegation re-used
  resolved ids (B-1/B-2) for new concerns without a re-open resolution →
  self-contradictory finalized review (aggregate_resolutions vs
  remaining_open_issues both faithful; contract permits the overlap —
  no `reopened` disposition, no FinalizedReview consistency rule).
  Item E written into `docs-local/plans/future-extensions.md` with scope
  sketch + open design decisions; webui/orchestration unchanged.
- jsdom gotchas recorded in Runbook 13: events must come from the jsdom
  window; `confirm` undefined on the node global.

Session 41 (2026-09-15, main PC — Phase 7 increment 1; local Docker stack
up throughout, no cloud actions, Cloud SQL STOPPED):
- Implemented the story picker + session creation per the Phase 7 plan:
  `webui/static/api.js` (fresh API client per D17-3: uuidv4
  Idempotency-Key persisted under `pending:create-session` before the
  fetch, 503 same-key retry with bounded attempts + backoff, error-envelope
  normalization, injectable fetch/storage/sleep for tests; body carries
  `requested_formats:["md","pdf"]`), picker UI in `app.js`/`index.html`/
  `app.css` (list + client-side search filter, hover/focus cached preview
  via detail GET rendered with the sanitized markdown renderer, confirm →
  POST /sessions with "reviewing…" spinner, session id persisted under
  `session:id` for increment-2 resume), 13 new vitest tests
  (test-first, `webui/tests/frontend/api.test.js`).
- Contract details caught live: `CreateSessionResponse` is flat
  (`session_id`/`state`, not nested); story rows key on `story_id`;
  409 active-story code is `STORY_SESSION_ACTIVE`.
- Layout iterated on owner feedback (three rounds, final version
  delegated to a gpt-5.6-terra subagent per owner request): header row
  with confirm button, foldable `<details>` list with live
  "stories (N) — selected: <title>" summary, compact inline radio rows,
  full-width preview below.
- **Browser gate PASS**: real flow-1 session on story-04 created from
  the browser (durable `sess-0e9c…` confirmed via proxy GET), reload +
  same story → 409 with the active-session hint. Two live-gate bugs
  fixed in-session: error path wrote to a hidden element; hint matched
  the wrong error code. Evidence + gotchas in Runbook 13 increment 1.
- Verification: `make webui-test` pytest **11 + vitest 15** (13 new);
  compose contract **20**; webui image rebuilt/redeployed four times
  (static files are baked into the image).


Session 40 (2026-09-15, main PC — Phase 7 increment 0; local Docker
compose stack up (incl. orchestration + webui as new compose services), no
cloud actions, Cloud SQL STOPPED throughout):
- **D17 amendment 1 recorded** (owner decision, chat): D17-1's "browser
  calls orchestration directly" was unworkable (no CORS on orchestration,
  D16 forbids adding it; no persistent orchestration endpoint existed).
  The webui FastAPI app gains a **thin same-origin /api reverse proxy** to
  `ORCHESTRATION_BASE_URL` (chosen for its fit to the GCP shape: one HTTPS
  LB path-routes /api → orchestration); **orchestration became a compose
  service** (`local-agents` profile, :8130) as the proxy target; browser
  libs vendored as the libraries' real ESM dists (import map, no bundler).
- Delivered `webui/` uv package 0.1.0 (config, app factory: /health,
  static shell, /api pass-through proxy with no client timeout,
  ORCHESTRATION_UNREACHABLE retryable 503, dot-segment guard), static shell
  (index/app.js/app.css + carried-over markdown.js + vendored
  dompurify/marked/remend), 11 pytest + 2 vitest, Dockerfile (dataset guard,
  non-root), `make webui-test`, compose `webui` (:8120, local profile) +
  `orchestration` (:8130, local-agents profile) services; Runbook 13 opened.
- **Browser gate PASS** (owner-driven): page loads, "orchestration:
  reachable" over the real /api/v1/stories read.
- Two live gotchas fixed + recorded: compose-postgres namespace clash
  (facilitator ADK `sessions` table) → separate `orchestration` database;
  MCP SDK DNS-rebinding 421 on in-network Host headers → compose sets
  `STORY/ARTIFACT/REPORT_SERVICE_URL` in-network URLs.
- Review (read-only subagent): 1 Critical (5 s default httpx timeout would
  503 live long turns) + 1 Important (raw /api/%2e%2e traversal escape) +
  minors — **all fixed in-session**, evidence in Runbook 13.

Session 39 (2026-09-11, main PC — docs-only replan; no cloud actions,
no local Docker, Cloud SQL STOPPED throughout):
- Owner decision **D16**: Phase 7 client is a **minimal Web UI**, not a
  TUI (owner confirmed a web interface is what is needed; scope =
  chat-style dialogue, pre-conversation story picker with hover
  preview, report download via signed URLs; no animations, no design;
  API consumed as-is, no server-side changes).
- Applied the design change in `docs/` (tech-stack Interface row,
  api-contract "Client interaction states", architecture, data-flow
  participant labels, repository-layout `tui/`→`webui/`, index);
  Phase 7 rewritten in development-plan; future-extensions Item B
  marked superseded; D16 recorded in local-decisions; AGENTS.md +
  HANDOFF references updated.
- **D16-3 starting point**: the existing vanilla-JS chat UI at
  `~/projects/homelab/cv-agent/src/cv_agent/static/`
  (`chat.{html,js,css}` + markdown renderer + JS tests) — reuse chat
  shell/message rendering, re-point API calls to orchestration
  endpoints with idempotency keys, add the story picker.
- Commits: `962928d` (docs, atomic) + `bb59420` (docs-local bundle) on
  main; `962928d` cherry-picked to `docs/initial-frozen` as `206208b`
  (clean). Owner to push both branches.

Session 38 (2026-09-13, main PC — Phase 6 increment 5 + close; local
Docker compose stack (real adapters + Vertex for the gate), throwaway
Postgres, no cloud actions, Cloud SQL STOPPED throughout):
- Owner decision **D15 amendment 3**: the exit-gate integration suite
  runs **fully live** (real adapters + Vertex, incl. a real 10-turn
  park arc) — ~35–50 model calls / 15–30 min accepted; model behavior
  steered via PO message, asserted on observables only; scripted
  truth-tables stay deterministic.
- Implemented `orchestration/tests/integration/` (conftest live
  fixture, helpers, flow-arc / park-at-10 / lease-contention tests) +
  `make orchestration-integration-test` (incl.
  ORCH_LIVE_GCS_PUBLIC_URL).
- Verification: orchestration **90+11s** (3 new live skips); live gate
  **PASS 3 passed in 366.95 s** after two test-side fixes (httpx sends
  `cursor: None` as empty string → follow cursor only when non-null;
  finalize replay regenerates fresh signed URLs → compare durable
  references). Regressions: review-schemas 154, agent-kit 86, agents
  4×4, business 6+2s, engineering 7+1s, synthesis 7+2s, facilitator
  3+1s, compose contract 20. Phase-close review **Ready-to-close**;
  M1 (PO-acceptance live coverage home documented) + M2 (timing
  assumption comment) fixed in-session, M3 noted. Phase 6 marked
  COMPLETE in development-plan.md. Throwaway-postgres race now 9
  observations.

Session 37 (2026-09-13, main PC — Phase 6 increment 4; local Docker
(compose stack recomposed with the dual-scheme fake-gcs for the live
gate; throwaway Postgres for the deterministic tier), real Vertex via
adapters for the live gate only, no cloud actions, Cloud SQL STOPPED
throughout):
- Implemented flows 3+4 per plan: `finalization.py` (flow-3 core:
  finalizing marker → deterministic finalized-review artifact → render
  per format → atomic completed+refs+canonical transaction;
  retryable-keeps-finalizing / non-retryable-rolls-back-to-active),
  gate-finalize + po_accepted wiring in `turns_flow.py` (acceptance
  bypasses facilitator, no count increment, synchronous finalize in one
  TurnResponse; same-key retry resumes flow 3; rejected new keys
  release their claim row), `finalize_api.py` (POST /finalize
  four-state table incl. under-lease re-read; GET /report
  REPORT_NOT_READY), completed SessionDetail reports,
  `signed_urls.py` (V4 HTTPS signed URLs, committed throwaway local
  signer, host rewrite to ORCH_GCS_PUBLIC_URL, warm-up at startup),
  `records_store.update_session` reference fields,
  `idempotency.release`, google-cloud-storage dep, compose fake-gcs
  `-scheme both` wiring, Makefile `orchestration-finalize-live-test`.
- **D15 amendment 2 recorded** (D15-5 settled empirically: fake-gcs
  dual-scheme HTTPS signed-URL path works; HttpsUrl shape made the
  unsigned-HTTP fallback impossible; finalizing turn-key semantics;
  15-min URL TTL).
- Verification: orchestration **90+8s**; review-schemas 154; agent-kit
  86; facilitator adapter 3+1s; agents 4×4; compose contract 20; image
  builds. Independent review: 4 Importants (artifact-save classification,
  IN_PROGRESS read-only bypass, finalizing same-key re-execution,
  finalize TOCTOU) + minors — **all fixed in-session** (findings +
  fixes in Runbook 12); focused re-review Ready to proceed.
- Live gate run and **PASS** (owner approval in chat): full session
  creation → po_accepted synchronous finalize → fresh report URLs →
  downloaded report bytes over signed fake-gcs HTTPS (63 s, ≈4 model
  calls). Live-only fixes: live env filter dropped
  ORCH_LIVE_GCS_PUBLIC_URL (signer fell back to ADC); jsonb string len
  in an assertion; the compose stack had gone down and was re-upped.

Session 36 (2026-09-13, main PC — Phase 6 increment 3; local Docker
(compose stack for the live gate; throwaway Postgres for the
deterministic tier), real Vertex via adapters for the live gate only,
no cloud actions, Cloud SQL STOPPED throughout):
- Owner decisions recorded (D15 amendment 1): adapter contract extension
  (option A — `FacilitatorRequest.invocation_id` + at-most-once result
  persistence per (session, invocation) + `GET /turn-result/...`
  reconciliation endpoint; binding got `PostgresTurnResultStore` on the
  ADK Postgres) and increment-3 finalize scope (option B — gate-finalize
  and `po_accepted` return retryable 503 until increment 4 wires flow 3;
  nothing persisted, claim stays in_progress).
- Implemented flow 2 per plan: `turns_flow.py` + `turn_execution.py` +
  `lineage.py` + `turns_api.py` (lease → claim → lineage-scoped input
  assembly → facilitator invocation with deterministic uuid5 invocation
  id → TurnRecord with stamped resolutions → delegation execution
  (both/business/engineering with previous review + extra context,
  parallel with sibling cancellation; reuse_previous/none) → at-most-once
  synthesis per turn (latest-per-perspective pairing) → gate precedence
  (park-at-10 → continue-on-synthesis → open-issues-empty finalize) →
  single TurnResponse; canonical replay re-reads resolutions from the
  TurnRecord), `HttpFacilitatorClient` between-attempts reconciliation
  (request-scoped closure), `records_store.update_session` +
  `idempotency.complete` transactional variants (atomic park + claim
  completion), Makefile `orchestration-turns-live-test`.
- Verification: orchestration **77+7s**; agent-kit **86** (+4);
  facilitator adapter **3+1s**; review-schemas 154; agents skeleton 4×4;
  both images rebuilt. Independent read-only review: 1 Critical
  (shared-client reconcile-target race) + 2 Importants (parked-session
  same-key replay lockout; missing facilitator AgentRunRecord) + 4
  minors — **all fixed in-session** (findings + fixes in Runbook 12).
- Live gate run and **PASS** (owner approval in chat): real session
  creation + one real dialogue turn (re-review message) over compose
  HTTP — 200 schema-valid TurnResponse, durable turn record + count,
  identical same-key replay, history reads (127 s). One live-only fix:
  `FACILITATOR_DB_URL` (`postgresql+asyncpg://`) normalized for asyncpg
  in `PostgresTurnResultStore`.

Session 35 (2026-09-13, main PC — Phase 6 increment 2; local Docker only
(throwaway Postgres; deterministic tier needs no compose), no cloud
actions, Cloud SQL STOPPED throughout):
- Implemented flow 1 per plan: `agent_clients.py` (frozen Phase 5 contract
  mirrors + observability-policy HTTP clients: short 60/3 jittered,
  facilitator 120/2 + 5 s, deadline clamping, 4xx never retried),
  `flows.py` (idempotency claim → get_story → uuid5-derived run/session
  ids → idempotent artifact saves with the client key → parallel reviewer
  fan-out with sibling cancellation → synthesis → facilitator opening
  turn with turn-1 assertions → TurnRecord + canonical response),
  `sessions_api.py` (POST/GET/GET detail, keyset cursor pagination),
  `db.py` pool lifecycle + /health database flag, records_store
  insert-or-get/list/touch additions, 4 adapter URLs in config, httpx in
  runtime locks, Makefile `orchestration-flow1-live-test`.
- Verification: orchestration **59 passed / 6 skipped**; review-schemas
  **154**; image builds. Independent read-only review: 4 Importants +
  several minors — all fixed in-session (naive-cursor 500, opening-turn
  assertion, synthesis audit input refs, malformed-5xx retryability,
  fan-out cancellation, backoff clamp, v4 key check, NOT_FOUND 404);
  deferred minors recorded in the runbook.
- Live gate run and **PASS** (owner approval in chat): real session
  creation on story-07 — 201 schema-valid `CreateSessionResponse`, 4
  AgentRunRecords, read paths, same-key replay (79.6 s). Two live-only
  fixes folded in: adapter route paths (`/invoke`, `/turn`) missing on
  the HTTP clients; adapter-response strict-JSON datetime parsing.
  Evidence + gotchas: Runbook 12 increment 2.

Session 34 (2026-09-13, main PC — Phase 6 increment 1 + Item D doc; local
Docker only — throwaway Postgres + compose local stack, no cloud actions,
Cloud SQL STOPPED throughout):
- Increment 1 per plan: `mcp_client.py` (streamable-HTTP wrapper, 60 s/3
  attempts, half-jittered 1 s/2 s backoff, retryable-code classification,
  remaining-deadline clamping with 5 s reserve, attempt-never-started rule),
  stories router (list/detail, orchestration-side title filter, 404/503
  envelopes), correlation middleware + validation-error normalization, real
  `/health` (story/artifact/report probe flags), Makefile
  `orchestration-stack-test` env-gated compose gate, `mcp==2.1.1` in locks.
- Verification: orchestration **43** (stack) / **38+5s** (plain);
  review-schemas 154 baseline; image builds. Review: **Ready to proceed**;
  Important (malformed correlation id → 500) and 3 minors fixed in-session.
- Also: Item D (callbacks/observability completion) added to
  future-extensions and committed (`7b2a06a`) with a HANDOFF marker (Phase 8
  sub-item). Evidence + gotchas: Runbook 12 increment 1.

Session 33 (2026-09-13, main PC — Phase 6 increment 0; local Docker only, no
cloud actions, Cloud SQL STOPPED throughout):
- Implemented increment 0 per plan/D15: `orchestration/` uv package (config,
  errors, app-factory + /health scaffolding, idempotency claim, turn lease
  TTL 6 min, asyncpg records_store — no ORM),
  `deploy/cloud-sql/migrations/0001_orchestration_records.sql` +
  `run-migrations.sh`, root-context Dockerfile, Makefile `orchestration-test`
  (throwaway postgres:16 + real migrations).
- Verification: **orchestration 19 passed**; review-schemas 154 (baseline
  unchanged); image builds and imports. Independent read-only review:
  **Ready to proceed**; minors fixed in-session, one deferred
  (run-migrations.sh DATABASE_URL in argv — revisit before Phase 8 cloud
  runs). Evidence + gotchas: Runbook 12 increment 0.

Session 32 (2026-09-13, main PC — Phase 6 opening; docs-only, no cloud
actions, Cloud SQL STOPPED throughout):
- Read the Phase 6 design set in full (api-contract, data-flow, schemas
  HTTP/records/MCP sections, observability, agents session semantics,
  repository-layout), then wrote the Phase 6 plan
  (`docs-local/plans/phase-6-orchestration.md`): increments 0–5 with live
  gates per agent-touching increment; exit gate = the development-plan
  integration criteria over `agents-compose-up`.
- **D15 recorded** (six increment-0 owner decisions, all approved in chat):
  orchestration/ uv package + compose wiring; ordered SQL migrations +
  asyncpg repository (no ORM); fake in-process agent clients for the
  deterministic tier (D13 extension — LLM behavior never scripted, MCP
  servers never faked), real-adapter live gates main-PC only; DB idempotency
  claim + stored canonical response (never signed URLs); fake-gcs signed-URL
  emulation verified empirically at increment 4 (fallback recorded if
  partial); facilitator reconciliation against the local adapter's Postgres
  session backend, mechanism confirmed at increment 3.
- Runbook 12 opened; commit `9aaa45a` (plan + D15 + runbook + this HANDOFF).

Session 31 (2026-09-12 — Phase 5 close-out, local only):
- Phase 5 completion review **Ready-to-close** (diff `67e7523..6b1e3bc`).
- Important fix: `agents-compose-up` ADC guard was dead code — split into
  two checks, re-verified. Minor: dead `json.loads` removed from
  `synthesis_adapter`. Phase marked COMPLETE in development-plan; Runbook 11
  completion-review section added.

Session 30 (2026-09-12 — Phase 5 increment 4 + exit gate):
- Facilitator agent + adapter (corrective re-prompts → DELEGATION_VALIDATION,
  lineage tool guard, Postgres session backend) and the `local-agents`
  compose profile (4 adapters, ports 8111–8114).
- **Phase 5 exit gate PASS**: example-interaction walkthrough (story-05
  partial-resolution) over compose HTTP; evidence + gotchas in Runbook 11 §4.
- D14 amendment 1 (token cap 16384, `corrective_reprompts` envelope field,
  dependency/credential shape). Increment-4 review Ready to proceed.

Earlier sessions: phase-level record above; full session detail is in
Runbooks 03–12 (each session's work, evidence, gotchas, and review findings
are recorded there), `docs-local/local-decisions.md` (D1–D15 and amendments),
and the git log.

## Verification and Review

Baseline (latest green run of every suite — re-verify against these counts
after changes):

- review-schemas **173** (session 47: +2 delegation_rationale_reply), ado-wire **7**, dataset **36**, mcp-ingress **7**,
  mcp-story **67**, mcp-artifact **32**, mcp-report **36**, compose contract
  **20** (session 40; re-run after compose changes), agent-kit **104**, agents skeleton **4×4**, business adapter
  **6+2s**, engineering adapter **7+1s**, synthesis adapter **7+2s**,
  facilitator adapter **3+1s**, orchestration **105+11s** (session 47: +5 Item G);
  **webui 12 + vitest 65** (session 48: +6); live gates: business/engineering/synthesis
  adapters + facilitator walkthrough all PASS (Runbook 11);
  orchestration flow-1, flow-2, and finalize live gates PASS (Runbook 12);
  webui browser gates PASS: increment 0 reachability, increment 1 picker +
  creation + 409 path, increment 2 dialogue turns + resume, increment 3
  acceptance → finalize → report download (Runbook 13).
- Per-session verification evidence (commands, counts, review verdicts,
  gotchas): append-only in the runbooks — Runbook 11 §0–4 + completion
  review for Phase 5; Runbook 10 for Phase 4; earlier phases in 03–09.
- Review discipline: independent read-only subagent review per significant
  increment and at phase close; verdicts recorded in the runbook sections.

## Remaining Tasks

- Deferred review minors (fix in Phase 6 where natural, else later):
  - Session 34: run-migrations.sh docker fallback startup race (first psql
    contact can fail after pg_isready; add a small retry).
  - Session 33: run-migrations.sh passes credentialed DATABASE_URL in argv
    (revisit before Phase 8 Cloud SQL runs; PGPASSWORD/env alternative).
  - Session 28: named-but-unmapped local deps in pyprojects; adapter generic
    handler maps model 400-class errors retryable; `previous_review_version`
    echo not cross-checked (contract doesn't require it).
  - Session 29: extract shared single-turn run loop from
    `run_reviewer`/`run_synthesis`; document mirror refs min/max asymmetry.
  - Session 31: reviewer shells → explicit `model_validate_json`; generic
    handler retryable-mapping (same as above); `_STORY_PATTERN` introspection
    brittleness; `extra_context` unbounded vs `Text`;
    `mcp_*_service_url` audiences → `home.tfvars` (Runbook 10 §5 gotcha).
  - Someday-minor: one-line RENDER_FAILED retryability clarification in
    docs/design/observability.md (atomic docs commit + frozen cherry-pick).
- **Item D (future-extensions) — callback/observability completion**: do not
  lose track of it. It is required design completion (evaluation.md callback
  requirement); plan its facilitator-first slice as an explicit sub-item of
  the **Phase 8** plan (Phase 8 already owns observability wiring). No Phase 6
  replan; the 50%/75% context-length policy is safe to defer — Phase 6 live
  gates are short turns.
- D9 deferred items: dataset fidelity/trimming decision; metadata
  semantic/display classification.
- Optional: fix broken glab git-credential helper path (cosmetic); tighten
  default compute SA `roles/editor` (pre-existing).
- CR→AE test gap recorded as a Phase 8 exit criterion (docs hardening,
  session 8).

## Next Steps

1. **Phase 7 increment 4 (exit gate + close)**: finish the owner-driven
   walkthrough on the story-07 session (`sess-f5e115d5…`, 2/10 turns;
   creation + delegated stages + Item G gate already covered — Runbook 13):
   remaining items are **mid-turn refresh resume** (reload while a turn is
   processing → persisted-body replay), **live park** (deferred from
   increment 3), and **accept → finalize stage + fresh report links +
   regenerate**. Then all regression suites, independent read-only review
   of the phase diff, Phase 7 COMPLETE in development-plan.md, Runbook 13
   completion review.
2. ~~Item G live gate~~ **DONE (session 48, PASS)** — evidence in
   Runbook 13 §Item G live gate.
3. Owner push `main` + `docs/initial-frozen` (identifier check re-ran
clean post-commit, session 45; re-run after this session's commits —
session 48 included webui/session evidence in the runbook).

## Important Notes

- **Commit rules**: conventional style, explicit paths only; `docs/` commits
  atomic and separate (frozen cherry-pick requirement); new files under
  `.agents/` need `git add -f`. Owner commits/pushes on request; agent never
  pushes. Destructive commands are owner-run only.
- **Evidence sanitization**: no persistent identifiers in git (runbooks,
  HANDOFF, commits) — use `$PROJECT_ID` / placeholder forms; identifier
  check (`git log --all -S "$PROJECT_ID"` after sourcing both env files —
  unset `$ADO_ORG` makes it a false match) is a mandatory pre-publication
  gate and must run after the last commit of the session performing it.
  History rewrites end at publication.
- **Cloud SQL is PAUSED** (STOPPED/NEVER): `make db-resume` before any phase
  needing it; remind to `db-pause` at wrap-up. Phase 6 needs it not — the
  compose Postgres substitute carries all orchestration state via the same
  migration files.
- **Machine split**: main PC has ADC/Vertex (all live gates, cloud); dev
  server has no ADC (deterministic work only).
- **Cost**: trial credits near-zero used of zł1,114, expire 2026-12-05;
  Phase 6 Vertex spend = integration-test calls only. ADO org: free plan,
  its free-trial Azure subscription must stay unused.
- **Azure DevOps ground truth** (Phase 3): org `$ADO_ORG` (gitignored
  `infra/envs/ado.env`), project `story-review` (Agile), ids 5–55,
  conventions in Runbook 08; re-export needs `$ADO_PAT` (`rest-verify`) or
  az fallback.
- Throwaway-postgres startup race now 8 observations (Runbook 12);
  run-migrations.sh small-retry fix stays due before Phase 8 cloud runs.
- **Local stack is UP, carries the D20+D21 code** (fully rebuilt session
  48; note: rebuilds wipe fake-gcs's memory-backend
  artifacts — old completed sessions' downloads 404, expected; compose
  Postgres is volume-backed and needs manual migrations — 0003 + 0004
  applied): orchestration (:8130) + webui (:8120) compose services; orchestration uses the separate
  `orchestration` database in the compose postgres. Compose Postgres
  active sessions: story-01/-03/-04/-06/-14/-15 + story-07
  (`sess-f5e115d5…`, 2/10 turns — the increment-4 walkthrough session).
  `agents-compose-down`
  when done. `compose-contract-test` needs `compose-up` first.
  Signed fake-gcs URLs point at `https://127.0.0.1:9026` (self-signed
  cert — accept the browser warning; recorded in Runbook 13).
- **Keep private** until final review; GitHub mirror pending (owner).
- Repo layout/plans/runbooks index: `docs-local/development-plan.md` and
  the per-phase plans under `docs-local/plans/`.
