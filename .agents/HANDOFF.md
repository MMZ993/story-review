# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D15),
`docs-local/development-plan.md` (phase scope/exit criteria), and git history
(the record of what changed). Do not let this file grow back into an archive.

Last updated: 2026-09-15 (dev server, **Phase 9 increment 2 COMPLETE —
dataset tuning pass: DATASET bucket empty (run 5: engineering-weak 0
failures = first fully passing case; unresolvable 11→3 via unpinned
artifact relaxation); ADO enriched (Feature 4 description + story-01
invoice-content sentence) + re-export; all remaining failures PROMPT-class
for increment 3. Evidence: Runbook 15 §Increment 2.**)

## Next Session

### Remaining Tasks

- Phase 9 increments 3–5 per plan (PROMPT-class backlog + judge wiring,
  Runbook 15 §Increment 2 run 5): delegation calibration (single-side
  where expected; never `both` in unresolvable dialogue turns;
  conversational resolution instead of delegation in
  conflicting/hidden-conflict), severity calibration (blockers everywhere
  vs info/major ceilings), open issues never empty at acceptance, conflict
  detection (synthesis `conflicts: []` on every case), facilitator story-MCP
  tool calls on comment scenarios, synthesis inputs-echo corruption
  (stochastic).
- **Web UI mobile fix (owner request, next session)**: story selection
  sits below the fold on mobile (Review Story button on top, story list
  at bottom, not visible) — plan a mobile-friendly arrangement (e.g.
  floating button).
- Deferred Phase-8 review minors (Runbook 14 §Increment 7): env-pointer/
  version runtime cross-check; compaction checkpoint-boundary +
  genai-Content test nits; per-call summarizer client.
- One live test session (`sess-8031e95b…`, story-09) left active on dev —
  its x-user-id wasn't persisted, cannot be abandoned from here (carry-over
  from increment 7).

### Next Steps

1. Phase 9 increments 3–5 per `docs-local/plans/phase-9-evaluation.md`
   (start at increment 3 — judged full set + prompt tuning loop).
2. Web UI mobile fix session (owner request).

   Note: dev Cloud SQL is RUNNING (owner request) — leave it up; the
   local compose stack is also intentionally left up.

### Verification and Review

This session (Phase 9 increment 2): dataset **37 passed** (+1);
evaluation **90 passed** (+3); run 5 full t1 with the **DATASET bucket
empty** (engineering-weak 0 failures; unresolvable 11→3); runbook +
HANDOFF updated; ADO diff owner-approved; `git diff --check` clean.
Remaining open doc item unchanged (evaluation-tests.md finding-key
wording).

Prior session (Phase 9 increment 1 + span fix): `make evaluation-unit-test`
**82 passed**; orchestration suite **207 passed / 12 skipped** (+1:
agent_runs record real invocation spans — reviewers overlap, synthesis
after both, facilitator after synthesis; `timed_invoke`/`TimedResult`,
owner-approved "fix timestamps only"); `make evaluation-test` fails
cleanly (exit 2) without a stack; `git diff --check` clean; compileall
ok; modules < 300 lines. Independent read-only review: 1 Critical +
5 Important + 6 Minor → all fixed in-session except the finding-key
wording deviation (Runbook 15 §Increment 1).
No cloud actions; Cloud SQL STOPPED throughout.

## Where we are

- **Phase 8 (Real GCP deployment & versioning proof) COMPLETE and
  CLOSED** (Runbook 14 increments 0–7, decisions D24–D28): everything
  live on GCP (webui/orchestration/MCP on Cloud Run, four AE agents,
  Cloud SQL, monitoring); versioning/rollback proof live; system
  reachable at the public domain. Remaining cleanup: D5 engine prune
  (owner-run).
- **Phase 7 (Web UI) COMPLETE and CLOSED** (sessions 39–50; increments 0–4
  + Items E/F/G + D18–D22, walkthrough gate PASS session 49, phase-close
  review session 50 Ready-to-proceed with findings fixed in-session.
  Detail: Runbook 13, D16–D22). D22 shipped session 50: `POST
  /sessions/{id}/abandon` (state table per api-contract) + webui abandon
  button + past-sessions list; the six legacy stuck compose sessions
  (story-01/-03/-04/-06/-14 active; story-15 was already completed — 409
  SESSION_READ_ONLY live) are parked and their stories released.
  Compose Postgres sessions remaining: story-13 second session active,
  plus parked/completed history.
- **Phase 6 — Orchestration (FastAPI): COMPLETE and CLOSED**
  (sessions 32–38; detail in Runbook 12, decisions D15 + amendments
  1–3). All gates green; live integration suite PASS (3 passed in 367 s).
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

Phase 9 increment 2 (2026-09-15, dev server; owner-approved direction +
spend; detail: Runbook 15 §Increment 2):
- **Representativeness walk** (8 aspects × 10 scenarios): all covered;
  oddity resolved — `completed` + `po_accepted:false` is the designed
  normal-readiness path (data-flow gate rule 3; example-interaction §5).
- **D-a**: unresolvable expected turns 2–9 unpinned (`produced_artifacts:
  null`); suite gained version-continuity + capture-based conflict
  pinning (test-first; evaluation 90, dataset 37).
- **D-b (owner: enrich ADO)**: Feature 4 description (post-purchase
  reliability) + story-01 invoice-content sentence; REST PATCH gotcha:
  JSON-Patch body must be an array. Re-exported; story MCP restarted
  (bind mount; no dataset-push for local).
- **Run 5**: DATASET bucket empty — engineering-weak 0 failures (first
  full pass), unresolvable 11→3; everything left is PROMPT-class.

Phase 9 increment 1, live t1 gate (2026-09-15, dev server; owner-approved
spend; detail: Runbook 15 §Live t1 gate):
- **Three CODE-class root causes fixed test-first, each verified by a
  live re-run**: (1) reviewer adapter strict-mode body validation
  rejected comment stories' ISO `created_at` strings → `model_validate_json`
  (agent-kit 148). (2) evaluation `db_evidence` vs the compose ADK
  `events` table shape (`event_data` jsonb + inner `content`; plus a
  row-key bug found at the rerun) → evaluation 87. (3) owner decision
  "list all artifacts per turn": flow-1/delegated/finalizing turns now
  record reviews/synthesis/finalized+reports; D19 catalog filters to
  synthesis-type refs (orchestration 207+12s; compose contract 20).
- **Run 4 verdict**: CODE bucket empty; remaining failures all
  PROMPT/DATASET (delegation calibration — never where expected yet
  always `both` in unresolvable; severity ceilings exceeded everywhere;
  open issues never empty; conflicts undetected; facilitator never
  reads comments; stochastic synthesis inputs-echo corruption).
- Compose gotcha: `agents-compose-up` recreated the Postgres volume on
  the first up (fresh `orchestration` db + migrations re-applied);
  later rebuilds preserved it.
- Stack left UP per owner instruction; web UI mobile fix recorded for
  a next session.

Phase 9 increment 1 code (2026-09-17, dev server; local only, detail: Runbook 15
§Increment 1):
- **Deterministic assertion engine delivered test-first (judge OFF)**:
  `capture.py` (typed CaseCapture), `orchestration_client.py` (webui
  idempotency discipline: key persisted before POST, 5 attempts, 503 /
  SESSION_LOCKED same-key retry honoring retry_after_seconds),
  `artifact_client.py` (minimal MCP JSON-RPC client for get_artifact,
  JSON+SSE), `db_evidence.py` (agent_runs + ADK events reads over the new
  compose postgres host port 127.0.0.1:15432), `case_runner.py` (replays
  po_script, captures turns/artifacts/audit/tool-trace, persistence
  probes incl. cross-run read rejection), `assertions/` package (turn
  structure, delegation, findings ceiling, pinned conflicts, final state,
  audit rows, MCP evidence, persistence), `runner.py` full suite mode
  (`--templates t1` default, per-case JSON artifacts, summary, exit 0/1/2).
- **Review findings fixed** (Critical suite-abort, retry/health/DSN
  minors, SSE decode, tests added).
- **Span fix (owner: "fix timestamps only")**: orchestration records
  real invocation spans; suite asserts the designed fan-out/ordering
  directly (only the reviewer pair may overlap).
- Live t1 gate + triage log pending owner spend approval.

Phase 9 increment 0 (2026-09-16, dev server; local only, detail: Runbook 15
§Increment 0):
- **Skeleton delivered test-first**: `prompts/judge.md` (five dimensions
0–4, blocker severity, strict-JSON JudgeResult reply); `tests/evaluation/`
package — `config.yaml` (gemini-2.5-pro, temp 0, candidate_count 1,
judge-md sha-pinned), suite-local `JudgeResult` models with the fixed
pass-rule validator, strict config loader, judge client (≤1 identical
retry on transient transport failure; invalid output / second failure =
case failed; no best-of-N ever), runner skeleton (config+sha check, stack
reachability, `--judge-smoke` live path).
- **Make targets**: `evaluation-unit-test` (21 passed), `evaluation-test`
  (clean exit 2 without a stack), `evaluation-smoke` (**live PASS**:
  passed=true, all dimensions 4/4, attempts=1; `vertexai=True` +
  `GOOGLE_CLOUD_PROJECT` env required — gotchas in Runbook 15).
- Judge `JudgeResult` kept suite-local per plan; moves to review-schemas
only if another unit consumes it.

Phase 9 planning (2026-09-16, dev server; docs-only, no cloud actions,
Cloud SQL STOPPED throughout):
- **D29 recorded** (owner, chat): (1) live demo **deferred until the whole
evaluation suite passes** — it opens the next phase; (2) **story tuning in
scope** — the 45-case matrix is iterated so the dataset better represents
all scenarios (edits in the ADO source of truth + re-export, never
hand-edited JSON); (3) **agent prompt tuning in scope**, re-proven by the
suite. No CI/CD (D24-1): `make evaluation-test`, the designed
`pipelines/evaluation.yml` stays documented intent.
- **Plan written**: `docs-local/plans/phase-9-evaluation.md` — verified case
matrix (10 scenarios; delegation/park/MCP-evidence/persistence mapping),
increments 0–5 with detailed mechanics: 0 judge+runner skeleton; 1
deterministic assertion engine (fixture-unit-tested assertions, CODE/
DATASET/PROMPT triage, `--templates t1` cheap subset); 2 dataset tuning
pass (ADO re-export, representativeness walk; flags: implicit re-review
conflict detection; `conflicting`/`hidden-conflict` expect completed with
`po_accepted:false` — confirm facilitator-gate finalize is intended);
3 judged full set + prompt tuning loop + smoke set; 4 dev-mode run
(Cloud SQL resume→pause, redeploy if prompts changed); 5 close (coverage
table, phase review).
- development-plan Phase 9 retitled "Evaluation suite & tuning" with
amended exit criteria (demo deferred per D29-1).
- Verification: case-matrix facts checked programmatically against
`dataset/expected/*.json`; no suites run (docs-only).

Phase 8 increment 7 — versioning/rollback proof + phase close (2026-09-16, dev
server; cloud actions owner-approved "please do increment 7"; detail: Runbook 14
§Increment 7):
- **Proof executed live**: new engine `facilitator-747d9d1`
  (`6251392106976247808`, HEAD commit, carries D28 compaction) — unit smoke
  PASS; orchestration re-point forward/rollback/forward, revisions
  `00031-xtj` / `00032-2xz` (old `573011d`) / `00033-x5t`, live flow-1 turn
  verified on each over the public domain. Final live = `facilitator-747d9d1`.
- **Regression battery green**: agent-kit 146, review-schemas 177,
  orchestration 206+12s, webui 25+89, agents 3/3/3/4, facilitator adapter
  3+1s, compose contract 20.
- **Phase-close review**: Ready-to-proceed; Important = codification (done:
  runbook/coverage/plan/HANDOFF); minors #2 fixed (`agents_env` stages
  `GOOGLE_GENAI_USE_VERTEXAI=1` — effective on the next agent deploy),
  #3–5 recorded in the runbook.
- Gotchas: `adk deploy` hangs on the telemetry prompt unless
  `adk telemetry disable` was run; one live test session (`sess-8031e95b…`,
  story-09) left active — its x-user-id wasn't persisted so it can't be
  abandoned from here.
- Cloud SQL left RUNNING; D5 prune (owner-run) is the remaining cleanup.

Prior sessions — see git history of this file and Runbooks 13–14.
Increment 6 close — live gate + live root causes (2026-09-16, dev
server; detail: Runbook 14 §Increment 6 close, D27):
- **Gate evidence**: structured request logs both services; app events
  (`gate_decision` ×5, `session_parked`); log-based metrics counting
  (gate 2/2, parked 1/1; alert metrics 0 points = healthy);
  **model_call telemetry live from Agent Engine** (duration/tokens/
  context level on the ReasoningEngine log); 503-same-key retry path
  observed live. `tool_call` events unobserved — see open item.
- **Fixes (test-first, all deployed)**: (1) stale pre-D19 MCP images →
  all three rebuilt + apply (plan gotcha: missing `-var` pointers
  DESTROY services); (2) AE facilitator root agent had no telemetry
  callbacks → wired + JSON handler (agent-kit 134; engines
  `1fb416d`/`17f73cd`, smoke PASS both); (3) live V4 signing impossible
  with token-only ADC → keyless IAM signBlob credential + fail-loud
  warm_up (orchestration 206+12s; gotchas: padded standard base64;
  deploy env list missing ORCH_SIGNER_EMAIL → metadata `default`);
  (4) report encoding: MD charset utf-8 + PDF em dash ` - `
  (mcp-report 38). Commits: `63f39f6`, `17f73cd`, `77e038b`,
  `2bf6122` + chore.
- **Owner pushed**: main → `1fb416d` early in the session; later
  commits to push at wrap-up.
Increment 6 slice C (prior session, detail Runbook 14 §Increment 6 slice C):
- **Code (test-first)**: `orchestration/app_events.py` — alertable
  events (`retry_exhausted`, `delegation_validation_failed`; emitted
  from the ApiError handler, one funnel for all routes) + gate/park
  events (`gate_decision` at `evaluate_gate`, `session_parked` after
  every atomic park transition: turns gate, abandon, flow-1 terminal
  failure). Drive-by: `_upstream` carries the agent name.
- **Terraform APPLIED**: `infra/modules/monitoring` — 4 log-based
  metrics over the structured events, the 2 designed alert policies
  (any-occurrence, auto-close 1h, **no notification channels — owner
  decision**), 1 `story-review` dashboard; logging+monitoring APIs
  enabled. Evidence + gotchas in the runbook (dashboard_json rejects
  promqlQuery; XyChart ≥2x2; no notification_rate_limit on metric
  policies; plan-without-`-var`-pointers destroys MCP services;
  `-target` does not prune a saved plan — 3 benign MCP revisions).
- **Review**: read-only subagent Ready-to-proceed; its minor (missing
  flow-1 park event) fixed in-session.
- **Verification**: orchestration **202 passed / 12 skipped** (+4);
  terraform fmt/validate clean; MCP services re-verified healthy
  post-apply. **Deployed this session**: orchestration + webui images
  (commits `ae5d723`/`d579e02`) — public domain health ok,
  `/api/v1/stories` 200, structured JSON logs live in Cloud Logging for
  both services, webui header `source repo` link live. Remaining: live
  trace gate + alert-metric observation (**next session** — drive one
  real turn from the browser; Cloud SQL left RUNNING for it).

Increment 6 slices A+B (2026-09-15, local, detail Runbook 14 §Increment 6):
- **Slice A**: structured JSON logging — `structured_logging.py`
  (JsonFormatter + idempotent configure_logging) in orchestration,
  webui, and agent-kit (three identical copies, deliberate across
  deploy units); request-logging middleware in both app factories
  (method/path/status/duration_ms/correlation_id (+user_id on
  orchestration; webui logs /api+/health only). Cloud Run stdout →
  structured Cloud Logging entries once deployed.
- **Slice B**: Item D facilitator telemetry — `agent_kit/telemetry.py`
  (context policy warn≥50%/summarize≥75%; paired content-safe
  before/after tool events; model latency/token events; ADK 2.8.0
  signatures verified), wired in `build_facilitator_runner`
  (guard-before-telemetry ordering) + `build_agent` callback params;
  `create_facilitator_app` configures the JSON handler.
- **Drive-by**: GitHub `source repo` link on the webui header
  (https://github.com/MMZ993/story-review), static, live on next deploy.
- **Deferrals (owner)**: 75% context compaction (mechanism decision —
  typed summary + session-history replacement; Item D remainder), and
  the flow-1-fix live re-test (folds into increment-6 live work).
- **Verification**: orchestration 198+9s, webui pytest 25 + vitest 89,
  agent-kit 133, agents 4×3-4, `git diff --check` clean. Nothing
  deployed.

Flow-1 fix deploy + D26 history purge (2026-09-14, dev server; cloud actions owner-approved in chat):
- **Deploy**: Cloud SQL resumed (`db-resume`, ~10 min to RUNNABLE — first deploy attempt failed the startup probe on a connector TimeoutError; transient cold-start race, retry succeeded). CR `orchestration` now runs the fix (image `20260914-…`, pre-D26 hash label `91d563a`). `/health` fully ok (first probe read degraded on scale-to-zero MCP cold starts — expected).
- **D26** (owner decision, explicit exception to the no-rewrite rule): `docs/source/{evaluation,topic}.md` purged from the **full history** of all branches via `git filter-repo --invert-paths`; `.gitignore` entry; files restored locally (ignored); `main`, `docs/initial-frozen`, `dev-server/session-23` force-pushed. Recorded in local-decisions D26. **Standing consequence: every hash recorded in HANDOFF/runbooks/local-decisions before 2026-09-14 is a stale label** (incl. the frozen-branch freeze label `d5cb413`); git log is authoritative.
- **Pushes**: owner-approved agent pushes — `main` → `7a8a168` (tip), `docs/initial-frozen` → `7d53ff5`; remote verified identical to local.
- Gotcha: `git filter-repo --force` discards uncommitted working-tree changes (the Runbook 14 deploy entry was lost and re-applied) — commit before rewriting.

Phase 8 increment 5, deploy part COMPLETE + environment move (2026-09-13,
dev server — now the PRIMARY machine; see WORKING_ENVIRONMENT.md):
- **Environment**: gcloud/az authed (ADC valid; az = no-subscription personal
  account, `az devops` works); env files + **terraform state** copied from
  the main PC — terraform runs here now.
- **Webui deployed publicly**: `https://story-review.mmz.sh` (Cloud Run
  `webui`, sa-webui, unauthenticated; `/api` proxy carries an ID token —
  `webui/webui/id_tokens.py`, `ORCHESTRATION_ID_TOKEN_AUTH`; orchestration
  stays IAM-gated; invoker binding lives in deploy.sh — recorded deviation).
  `sr_user` cookie `secure` behind TLS. Domain: `mmz.sh` Search-Console
  verification (TXT) + `domain-mappings` CNAME `ghs.googlehosted.com`;
  cert issued after Google's retry cycle. Full chain verified live.
- Commits `1d66551` (feat) + `f0a1e97`/`6310eb1` (deploy.sh fixes) —
  **owner pushes main**. Runbook 14 §Increment 5 = full evidence.
- Verification: webui pytest **22 (+4)** + vitest **89 (+2)**; review
  Ready-to-proceed (minors fixed/recorded).

Phase 8 increment 4 cloud part COMPLETE (2026-09-13, main PC; cloud
actions owner-approved "lets do 1,2,3,4", gate later delegated):
- **Orchestration on Cloud Run**: `cloudsql-iam:///` DSN → Cloud SQL
  IAM connector-backed asyncpg pool (`cloudsql_db.py`); MCP calls carry
  audience-scoped ID tokens (`id_tokens.py`, `ORCH_MCP_ID_TOKEN_AUTH`);
  `deploy/cloud-run/orchestration/deploy.sh` (+ gitignored `.env`
  AE pointers) — service `orchestration`, sa-orchestration,
  no-unauthenticated, timeout 600, 0–2 instances.
- **CR→AE gate PASS**: `/health` fully ok (database + all three MCP
  services from CR); flow-1 creates 201 in 55–72 s on six stories —
  all four agents invoked via `:streamQuery?alt=sse`; one AE session
  per review session in the Cloud SQL runtime store with the turn's
  events readable back (option-B reconciliation surface proven);
  user-scoping 422/404 evidence; D22 abandon proven live on CR.
- **Nine live root causes found+fixed at the gate** (each test-pinned;
  see Runbook 14 inc 4): asyncpg connect-callback args; mcp 2.1.1
  no-headers transport; MCP audience = service root (both sides);
  async `to_thread` token helper; **AE sessions live behind the runtime
  `:query` methods, NOT the control-plane `/sessions` REST routes
  (D25 session-route assumption amended)**; `:query` `output` envelope;
  `_IdTokenAuth` must subclass httpx.Auth + refresh at mint;
  `get_session` config-input returns zero events.
- **Facilitator redeploys** (clean labels, all SMOKE PASS):
  `facilitator-a7257a3` → `3b61a75` → `dc95165` (current pointer,
  engine `<fac-eng-3>`); 3 more retained engines for the D5 prune.
- **Review**: round 1 Critical (pool.close `__slots__` crash — caught
  pre-deploy) + round 2 Ready-to-proceed (9 minors; 3 fixed, rest
  deferred in the runbook).
- **Verification**: orchestration **191+12s** (+31), agent-kit **125**
  (+3); identifier check clean. ~18 commits (2 feat + fixes); owner
  pushes main.

Phase 8 increment 4, local part COMPLETE + D25 planning (2026-09-14,
main PC; no cloud actions, Cloud SQL left RUNNING):
- **D25 recorded** (owner, chat): all four agents invoked via AE from
  deployed orchestration (env-selected `ORCH_AGENT_MODE=http|ae`);
  reconciliation = option B (session-store read-back); breakdown in
  plan §4. D25 amendment 1: matcher keys on the rendered turn marker
  (digit-bounded), reviewer/synthesis user_ids are per-invocation.
- **AE clients** (`orchestration/orchestration/ae_client.py`): raw REST
  `:streamQuery?alt=sse` over httpx + ADC bearer (no aiplatform SDK —
  timeout control + no ADK dep); concatenated-JSON event parsing with
  `data:` tolerance; retryable-envelope retries per the shared policy;
  exhausted retryable envelopes keep `AgentCallFailure`; invalid final
  reply → terminal `VALIDATION_ERROR`; `DeadlineExceeded` propagates;
  facilitator = one AE session per review session (user_id = session id,
  list-or-create over REST `/sessions`) + option-B reconciliation
  (read `…/sessions/{id}/events`, reuse last own-turn reply — no second
  model attempt). AE audit fields: agent_version = engine deploy label
  from env, prompt_sha256 = sha256(rendered message),
  corrective_reprompts = 0 (loop is inside the deployed agent).
- **Mirrored renderers** (`ae_messages.py`, duck-typed): byte-identical
  to agent_kit renderers, pinned by equivalence tests in the agent-kit
  suite (`test_ae_message_mirrors.py`).
- **Config**: `ORCH_AGENT_MODE` + 8 `ORCH_AE_*_RESOURCE/_VERSION` vars
  (adapter URLs optional in ae mode); `default_agent_set` branches.
- **Review**: read-only subagent round 1 (1 Critical — facilitator
  missing the stream transport seam in `ae_agent_set`; 2 Important —
  retryable envelopes never retried, shared reviewer user_id; + minors)
  — all fixed; focused re-review confirmed fixes, N1 (envelope
  swallowing at exhaustion) + test gaps fixed and pinned. Deferred
  minor: `ae_client.py` ~530 lines exceeds the ~300 guideline (split
  matcher/parsing if touched again); N4 extra `/sessions` GET on the
  facilitator recovery path (cosmetic).
- **Verification**: orchestration **160+12s** (+31), agent-kit **122**
  (+5); `git diff --check` clean. Committed `4d5cd59` `feat:`; docs-local
  (D25 + amendment, plan §4) in the wrap-up `chore:` commit.

Phase 8 increment 3 COMPLETE (2026-09-13, main PC; cloud actions with
owner approval — "finish increment 3"):
- **All four AE agents SMOKE PASS** (real Vertex, strict-schema
  outputs): business `207561407045042176`, engineering
  `8786074272255705088`, synthesis `669180368850518016`, facilitator
  `5457914147628908544` (`-dirty`; N-1 good facilitator `7344922391497146368`).
- **Facilitator root causes** (four deploy iterations, Runbook 14 inc 3
  session 2): leftover `_ENGINES` NameError; **connector 1.22 sync
  `connect` inside a running loop deadlocks it — async drivers must use
  `connect_async`**; IAM asyncpg needs an explicit `user` and AE compute
  creds report `service_account_email == "default"` (metadata-server
  resolution, off-loop); per-call connector must be `close_async()`d.
  Raw `:query` REST surfaces error bodies the SDK hides.
- **Persistence proven**: ADK tables in Cloud SQL `facilitator` DB
  (owner sa-facilitator), `list_sessions` over `:query` returned smoke
  sessions created by a *previous* engine; smoke now deletes its
  sessions (finally) and the two evidence rows were cleaned.
- **Review**: read-only subagent **Needs fixes** → all 4 Importants
  fixed (deploy-failure masking in common.sh, connector leak, dirty-tree
  version labels guarded with `-dirty` opt-in, module-level extraction +
  6 new tests) + 4 minors fixed (smoke session cleanup, dead code,
  to_thread metadata fetch, admin-bootstrap input validation).
- **Verification**: agent-kit **117**; final redeploy + facilitator
  smoke PASS. D24 amendment 2 (AE lineage-guard deferral) recorded.
- **Session-2 admin note**: postgres role `<owner-email>` created in the
  `facilitator` DB for the local IAM-connect repro — optional owner-run
  `drop role` cleanup (Runbook 14).
- **Committed**: `ee63a04` `feat:` (ae_runtime fixes + tests, deploy
  scripts, smoke cleanup, admin-bootstrap validation, terraform IAM,
  run-migrations PGSSLMODE, Makefile) + `a16a896` `chore:` (Runbook 14,
  D24 am 2, HANDOFF); identifier check clean. Owner pushes main.

Phase 8 increment 2 complete + increment 3 session 1 (2026-09-12, main
PC; cloud actions with owner approval in chat):
- **Increment 2 (Cloud SQL live) — GATES PASS** (detail Runbook 14 inc 2;
  summary): run-migrations.sh docker fallback forwards `PGSSLMODE`
  (test-first; orchestration **129+12s**); `admin-bootstrap.py`
  (connector admin session, D7); databases `orchestration` +
  `facilitator` created with schema grants; migrations 0001–0005
  applied over IAM **as sa-orchestration** through the Cloud SQL Auth
  Proxy; orchestration asyncpg pool smoke against Cloud SQL PASS.
  Terraform: `roles/cloudsql.client` for the four IAM-login SAs.

Pre-increment-2 summary (increments 0+1, 2026-09-21):
- **Increment 0**: run-migrations.sh deploy fixes — DATABASE_URL parsed
once into libpq PG* env (`dsn_to_pg_env`, percent-decoded, query params
rejected; docker fallback forwards only set vars) so no credential ever
reaches argv; first-contact retry around the bootstrap (env-tunable);
script sourceable; `test_run_migrations.py` (parser + full-script run
through a DSN-detecting psql wrapper — skipped here, no local psql, so
the Makefile target exercised the docker fallback).
- **Increment 1 (user scoping, D24-3)**: review-schemas 0.9.0 → 0.10.0
(`UserId`; `user_id` on StoryRun/SessionRecord); migration **0005**
(`user_id uuid not null` both tables, legacy rows under sentinel
`00000000-…0000`, per-(user, story) active index **same constraint
name** so 409 mapping unchanged); orchestration `users.py` dependency
(422 on missing/malformed/non-v4 header) on all session routes
(stories/health exempt), ownership-scoped `get_session`/`list_sessions`
(cross-user → 404), flow-1 idempotency fingerprint includes user_id
(cross-user key replay → 409 REUSED); webui proxy forwards `x-user-id`,
new `user.js` 90-day sliding `sr_user` cookie + `X-User-Id` on every
api.js call, boot refresh.
- **Live gate PASS** (compose, migration 0005 hand-applied like 0003/0004,
images rebuilt): no header → 422; two users on story-02 → two 201s
(≈44 s each, real flow 1); scoped lists 1/1; cross-user detail 404 vs
owner 200; same-user re-create 409 STORY_SESSION_ACTIVE; sentinel user
sees all 15 legacy sessions; both gate sessions abandoned (parked).
- **Review**: read-only subagent **Ready to proceed** (no Critical) —
Important here-string swallowed parser failures (fixed: `|| exit 2` +
empty-parse guard, verified rc=2) + a stories-exemption test added;
minors deferred (cookie `secure` → increment 5 behind TLS; bootstrap
retry masks non-connection errors; migration-name interpolation).
Evidence + dispositions: Runbook 14.
- **Verification**: review-schemas **177**, orchestration **128+12s**,
webui **pytest 14 + vitest 87**, compose contract **20**. Commits:
`81baefd` (feat: schemas bump, migration 0005, orchestration scoping,
webui cookie/header, run-migrations.sh fixes + all tests) and `984953c`
(chore: Runbook 14 + HANDOFF). No `docs/` changes → no frozen cherry-pick
due. Identifier check clean (0 hits). Owner pushes main.

Phase 8 planning (2026-09-21, main PC; docs-only, no compose/cloud
actions, Cloud SQL STOPPED):
- **D24 settled** (owner, chat): no CI/CD this phase (make-driven local
deploys); webui deployed to Cloud Run under the owner's Cloudflare
`mmz.sh` subdomain via the same-origin `/api` proxy; **anonymous
multi-user scoping** (user_id on sessions/story runs, migration 0005,
90-day sliding cookie, no auth, 90-day retention via owner-run purge
make target); Item D **facilitator-first**; AE pruning per D5 after the
versioning proof.
- **Plan written**: `docs-local/plans/phase-8-gcp-deployment.md`
  (increments 0–7); Runbook 14 opened; D24 recorded in local-decisions;
  development-plan Phase 8 + this HANDOFF updated. Increment 1 adds user
  scoping before any deployment.
- **User-scoping docs change applied**: `X-User-Id` (UUID v4) convention +
  per-user scoping in `api-contract.md`, `UserId` type + `user_id` on
  StoryRun/Session records + per-(`user_id`,`story_id`) constraint in
  `schemas.md`, unauthenticated-demo stance in `deployment.md` — commit
  `8ad3570` on main, cherry-picked clean to `docs/initial-frozen` as
  `06deff0` (via temp worktree).
- **D24 amendment 1**: deployed facilitator ADK session store = Cloud SQL
  PostgreSQL `DatabaseSessionService` (IAM login); local runs keep the
  local/compose Postgres. Increment-3 open point closed.
- **Commits** (owner pushed both branches): `8ad3570` (docs, atomic) +
  `9c315c1` (docs-local bundle: plan, D24 + amendment, Runbook 14,
  development-plan, HANDOFF). Identifier check clean. No code, compose,
  or cloud actions; Cloud SQL STOPPED throughout; local stack still up.

Pre-Phase-8 Web UI presentation pass (2026-09-12, main PC; no compose or
cloud actions, Cloud SQL remains STOPPED):
- **Web UI**: replaced browser-default styling with a compact, responsive
  GitHub-dark presentation: clearer cards, hierarchy, controls, picker/session
  rows, accessible focus states, readable chat bubbles, green send/reachable
  status, a blue-accented primary story-selection panel, and footer
  `@ 2026 Marcin Żak / mmz.sh` with an `https://mmz.sh/` link. No client
  behavior or API calls changed.
- **Decision**: D23 records this owner-requested presentation-only exception
  to Phase 7's former no-styling-beyond-usability MVP scope.
- **Verification**: `make webui-test` PASS — pytest 13 and vitest 77;
  `git diff --check` PASS. Running compose still serves the prior baked image;
  owner may run `make agents-compose-up` to preview this pass.

Post-Phase-7 UI/UX follow-up (2026-09-12, main PC; local Docker stack
rebuilt, no cloud actions, Cloud SQL STOPPED):
- **Web UI**: picker resume/open controls moved left; header now says
  "FastAPI backend" on one line; story previews normalize the plain-text
  story projection into sanitized Markdown paragraphs; accept/finalize moved
  below the send row alongside abandon/choose-story controls.
- **Comment-story fix**: stories endpoint now validates the story-MCP JSON
  through Pydantic's JSON boundary, so strict timestamp fields in comments
  no longer produce an invalid-payload 503. Regression test added.
- **Verification**: webui **pytest 12 + vitest 77**; orchestration **117 +
  11 skipped**. The first orchestration run hit the known throwaway-Postgres
  startup race before tests; the rerun passed. `make agents-compose-up`
  rebuilt the full local stack; webui health is OK and story-43 returned
  200 with three comments. Evidence: Runbook 13 §Post-Phase-7 UI/UX
  follow-up.

Session 50 (2026-09-20, main PC — **D22 implementation + Phase 7 close**;
local Docker stack, images rebuilt twice, no cloud actions, Cloud SQL STOPPED):
- **D22 test-first**: review-schemas 0.8.0 → 0.9.0 (`AbandonSessionResponse`,
  +3); orchestration `abandon_api.py` (+10 tests — full state table, story
  release incl. 201-on-same-story, same-key replay, lease contention,
  stale-claim release, non-v4 key, stage clearing) with drive-by fix of a
  latent `records_store.update_session` no-conn-branch crash (`None` passed
  to `_retire_story_run`); webui `abandonSession` + abandon button
  (active/finalizing, confirm) + `renderPastSessions` picker list (+9
  vitest).
- **Live**: five stuck active sessions parked via the new endpoint,
  story runs verified `parked`; story-15 already completed → 409
  SESSION_READ_ONLY (live terminal-branch evidence).
- **Phase 7 close**: full regression battery at/above baseline
  (review-schemas 176, orchestration 116+11s, webui 12+76, all others
  unchanged); independent phase review (subagent, `b8a1416..HEAD` + tree)
  **Ready-to-proceed** — Important (missing public export of
  `AbandonSessionResponse`) + 2 minors, all fixed in-session, suites
  re-run green; Phase 7 COMPLETE in development-plan. Evidence: Runbook 13
  §Session 50.

Session 49 (2026-09-12, main PC — **increment-4 walkthrough + story-run release
fix + D22 docs**; local Docker stack, images rebuilt twice, no cloud actions,
Cloud SQL STOPPED):
- **Exit-gate bug found at the walkthrough**: completed/parked sessions never
  released their story (new session → 409 `STORY_SESSION_ACTIVE` forever) —
  `story_runs.state` was never transitioned (park + finalize wrote only the
  session row; the partial index excludes terminal run states). Fixed in
  `records_store.update_session` (single chokepoint, same transaction;
  test-first). Orchestration **106+11s**; 4 stale compose rows backfilled;
  image rebuilt; live 201 through the webui proxy.
- **Walkthrough PASS** on a fresh story-07 session: delegated turns 2–4,
  mid-turn refresh (functionally carried by persisted body + key; the
  passive-view pending PO bubble fix deferred as minor debt — D22-4,
  test-covered but the owner's browser still showed old behavior,
  suspected caching), accept → finalize → both reports + regenerate
  (fresh signed URLs verified), live park at turn 10 (story-13, run also
  `parked` — fix verified live), restart-on-same-story (new session,
  no 409). Evidence: Runbook 13 §Increment 4.
- **D22 recorded + docs applied** (owner decisions): `POST
  /sessions/{id}/abandon` (park-now for stuck active/finalizing sessions;
  `AbandonSessionResponse`; no new error codes) + webui historical-sessions
  view; parallel active sessions per story rejected. Docs: api-contract,
  schemas, architecture; frozen cherry-pick due.
- Verification: orchestration **106+11s**, webui **pytest 12 + vitest 67**
  (+2); both images rebuilt + redeployed.

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

- review-schemas **177**, ado-wire **7**, dataset **36**, mcp-ingress **7**,
  mcp-story **67**, mcp-artifact **32**, mcp-report **36**, compose contract
  **20** (session 40; re-run after compose changes), agent-kit **125** (inc 4 cloud: +3 auth/audience; prior 122), agents skeleton **4×4**, business adapter
  **6+2s**, engineering adapter **7+1s**, synthesis adapter **7+2s**,
  facilitator adapter **3+1s**, orchestration **191+12s** (inc 4 cloud: +31; prior 160+12s); **webui 22 + vitest 89** (inc 5: +4 pytest, +2 vitest); live gates: business/engineering/synthesis
  adapters + facilitator walkthrough all PASS (Runbook 11);
  orchestration flow-1, flow-2, and finalize live gates PASS (Runbook 12);
  webui browser gates PASS: increment 0 reachability, increment 1 picker +
  creation + 409 path, increment 2 dialogue turns + resume, increment 3
  acceptance → finalize → report download, increment 4 walkthrough (Runbook 13).
- Per-session verification evidence (commands, counts, review verdicts,
  gotchas): append-only in the runbooks — Runbook 11 §0–4 + completion
  review for Phase 5; Runbook 10 for Phase 4; earlier phases in 03–09.
- Review discipline: independent read-only subagent review per significant
  increment and at phase close; verdicts recorded in the runbook sections.

## Remaining Tasks

- Deferred review minors (fix where natural, else later):
  - Phase 8 inc 0+1 review (Runbook 14): `sr_user` cookie `secure`
    attribute — add at increment 5 (local compose origin is plain HTTP);
    run-migrations.sh bootstrap retry masks non-connection errors behind
    the generic message; migration-name string interpolation in the
    tracking insert (repo-controlled filenames).
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

1. **Walkthrough (owner, browser)**: resume increment-5 at `https://story-review.mmz.sh` — story-01 abandon + fresh-key retry (exercises the deployed fix); two-user cookie-scoping proof (normal + incognito window). **`make db-pause` after** (Cloud SQL left RUNNING for this).
2. Later increments 6–7 per `docs-local/plans/phase-8-gcp-deployment.md`;
   D5 prune (owner-run) also covers the 15 broken/superseded facilitator
   engines listed in Runbook 14 inc 3.
3. Housekeeping when local stack no longer needed: `make
   agents-compose-down`; local `cloudsql-proxy` container can be removed
   (`docker rm -f cloudsql-proxy`) once no more migration runs are due.

Pre-existing items folded into the plan: run-migrations argv/retry minors
(fixed inc 0), Item D observability (increment 6), CR→AE test gap
(increment 4).

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
- **Cloud SQL left RUNNING at wrap-up (owner wants the walkthrough next)** — pause with `make db-pause` (prefix `CLOUDSDK_CORE_PROJECT=$PROJECT_ID`) once the walkthrough is done.
  Standing rule: `make db-resume` before any phase needing it. **Billable Agent Engine resources now: 3
  current reviewers + current facilitator (`facilitator-dc95165`) + 3
  superseded good facilitators (incl. N-1) + 15 broken facilitator
  engines** — all awaiting the D5 owner-run prune at increment 7. Plus
  the new Cloud Run `orchestration` service (min-instances 0).
- **Machine split (updated)**: **dev server is now the primary** — ADC,
  terraform state, env files all present; cloud actions run from here.
  Main PC accessible read-only over NFS
  (`/mnt/admin-storage/projects/capstone_project`) — never run git or
  terraform against that path. Its az/ADC state is untouched.
- **Cost**: trial credits near-zero used of zł1,114, expire 2026-12-05;
  Phase 6 Vertex spend = integration-test calls only. ADO org: free plan,
  its free-trial Azure subscription must stay unused.
- **Azure DevOps ground truth** (Phase 3): org `$ADO_ORG` (gitignored
  `infra/envs/ado.env`), project `story-review` (Agile), ids 5–55,
  conventions in Runbook 08; re-export needs `$ADO_PAT` (`rest-verify`) or
  az fallback.
- Throwaway-postgres startup race now 10 observations (Runbook 12/13 +
  this session); the run-migrations.sh bootstrap retry now covers it.
- **Local stack was UP for the increment-1 live gate, then exited cleanly**
  (host stop after the session's gate; all 10 containers Exited(0), volume-
  backed Postgres + fake-gcs data intact). Restart with `make
  agents-compose-up`. It carries the Phase 8 increment-0+1 code (both
  images rebuilt this session; migration **0005** applied to the volume-
  backed compose Postgres — all five migrations now recorded): orchestration
  (:8130) + webui (:8120). Compose sessions: completed story-02/-05/-07/
  -09; parked story-13 (turn 10) + the five session-50 abandons + the two
  increment-1 gate sessions (story-02, test users `1111…`/`2222…`);
  active story-13 second session; 15 legacy rows grouped under sentinel
  user `00000000-0000-4000-8000-000000000000`. `agents-compose-down` when
  done. `compose-contract-test` needs `compose-up` first. Signed fake-gcs
  URLs point at `https://127.0.0.1:9026` (self-signed cert — accept the
  browser warning; recorded in Runbook 13).
- **Keep private** until final review; GitHub mirror pending (owner).
- Repo layout/plans/runbooks index: `docs-local/development-plan.md` and
  the per-phase plans under `docs-local/plans/`.
