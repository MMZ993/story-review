# Runbook 15 — Evaluation suite & tuning (Phase 9)

Plan: `docs-local/plans/phase-9-evaluation.md`. Decisions: D29. Local-only
increment 0 — no cloud actions, no compose actions, Cloud SQL STOPPED
throughout. The only Vertex spend: the live judge smoke (two calls total
— see below).

## Live judge smoke (owner-approved, 2026-09-16)

`make evaluation-smoke` (with `GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=$REGION` from `home.env`) — **PASS**:
`passed=true`, all five dimensions 4/4, no issues, attempts=1, publisher
`gemini-2.5-pro`; config sha `8323bbd0a5de…` matches `prompts/judge.md`.
Artifact: `tests/evaluation/artifacts/judge-smoke-clean-story-05.json`
(gitignored). Total spend: two calls (first run + the fix re-run).

Gotchas learned (all fixed in-session):
1. `genai.Client(location=…)` without `vertexai=True` targets the Gemini
   API and raises "Gemini API does not support project/location" — the
   agents get Vertex via the `GOOGLE_GENAI_USE_VERTEXAI=1` env var; the
   judge client passes `vertexai=True` explicitly.
2. ADC cannot resolve the project on this machine without
   `GOOGLE_CLOUD_PROJECT` (+ `GOOGLE_CLOUD_LOCATION`) exported — same
   requirement `scripts/smoke_vertex.py` documents. The make targets
   assume they are set (sourced from `infra/envs/home.env`).
3. The judge self-reported `judge_model: "gpt-4-turbo"` (hallucinated
   identity) in the first run. Fix: the case input now carries `case_id`,
   `prompt_sha256`, and `judge_model`, and the prompt requires copying
   them verbatim; the re-run echoed the configured model correctly.

## Increment 0 — judge + runner skeleton (2026-09-16)

Deliverables (all test-first; 21 unit tests, no model calls):

- `prompts/judge.md` — judge prompt: five dimensions 0–4
  (`review-coverage`, `grounding`, `conflict-resolution`, `delegation`,
  `final-state`), issue severities incl. `blocker`, strict-JSON
  `JudgeResult` reply shape, no shared agent state.
- `tests/evaluation/` package (pattern of `tests/contract`):
  - `config.yaml` — model `gemini-2.5-pro`, location `europe-west4`,
    temperature 0, candidate_count 1 (loader rejects anything else —
    no best-of-N), `prompt_path: prompts/judge.md` pinned by
    `judge_md_sha256` = sha256 of `prompts/judge.md`
    (`8323bbd0a5de…`, updated after the judge-model fix). Regenerate the
    hash after any judge prompt edit — the loader fails loudly on drift.
  - `evaluation/models.py` — suite-local `JudgeResult` (+ issues/scores)
    mirroring `docs/design/schemas.md` §JudgeResult incl. the fixed
    pass-rule validator (min ≥ 3, mean ≥ 3.5, no blocker). Suite-local
    per the plan; moves to review-schemas only if another unit consumes
    it.
  - `evaluation/judge_config.py` — strict loader (agent_kit
    `load_agent_config` pattern: exact key set, no defaults). Note:
    `prompt_path` resolves against config.parents[2] — the repo root for
    the shipped layout.
  - `evaluation/judge_client.py` — injectable transport; fixed policy:
    ≤1 identical retry on transient transport failure
    (`JudgeTransportError`), invalid structured output or second failure
    = `JudgeFailure` (case failed), never more than two samples. Live
    transport = google-genai ADC (like the agents), JSON mime type;
    4xx → non-retryable, 5xx/connection → retryable; records publisher
    model metadata (`response.model_version`, falling back to config
    model).
  - `evaluation/runner.py` — skeleton: verifies judge config (sha) first,
    then either `--judge-smoke` (one live judge call on the canned
    `judge_smoke_case.json` clean transcript; artifact to
    `tests/evaluation/artifacts/`, gitignored) or checks orchestration
    `/health` and reports "case execution arrives in increment 1". Exit
    2 on setup problems (clean failure without a stack).
  - `requirements.in`/`requirements.lock` (uv pip compile; pytest, pyyaml,
    httpx, google-genai), `pyproject.toml` (pytest pythonpath).
- `Makefile`: `evaluation-unit-test` (no stack, no model calls),
  `evaluation-test` (compose stack; skeleton), `evaluation-smoke`
  (one live judge call — spend).
- `.gitignore`: `tests/evaluation/artifacts/`.

Verification: `make evaluation-unit-test` → **21 passed**;
`make evaluation-test` without a stack → clean exit 2 ("orchestration
unreachable"); `git diff --check` clean; py_compile/yaml/json/toml
syntax checks ok. Judge prompt sha cross-checked by
`test_shipped_repo_config_loads`.

Open: none for increment 0 (live smoke done, see above). Increment 1 =
deterministic assertion engine + case runner against compose.

## Increment 1 — deterministic assertion engine (judge OFF)

Status: **code complete + unit-tested; live t1 run pending owner spend
approval** (each case = real agent turns on Vertex). This entry will be
updated with the run evidence + triage log after the live gate.

Deliverables (test-first; 66 unit tests incl. the 21 from increment 0):

- `evaluation/capture.py` — typed `CaseCapture` (persisted TurnView list,
  final SessionDetail, artifact contents keyed `type#vN`, audit-row
  evidence, facilitator tool-call names, persistence probes).
- `evaluation/orchestration_client.py` — HTTP client over compose
  orchestration with the webui discipline (api.js): v4 `x-user-id` per
  run, v4 `Idempotency-Key` persisted before every POST, bounded same-key
  retry on any 503 or 409 `SESSION_LOCKED` (4 attempts, linear backoff);
  non-retryable status → `OrchestrationError` with body evidence.
- `evaluation/artifact_client.py` — minimal MCP streamable-HTTP JSON-RPC
  client (initialize → initialized → tools/call) for `get_artifact`
  against the local artifact service (:8102, auth disabled). Handles
  JSON and SSE-framed responses; structured tool errors →
  `ArtifactToolFailure(code, message)`.
- `evaluation/db_evidence.py` — read-only Postgres queries over the new
  compose host port: `agent_runs` rows for a session (orchestration db)
  and the facilitator ADK session-event trace (facilitator db; events
  table + columns discovered at runtime — ADK-version tolerant; extracts
  `function_call` names from event content parts).
- `evaluation/case_runner.py` — replays `po_script` verbatim (create =
  opening turn; each entry one turn; `po_accepted:true` = acceptance
  turn), then reads every artifact version, the audit rows, the tool
  trace, and runs persistence probes (session restore via GET detail,
  same-run artifact read ok, cross-run read under a foreign `run-uuid`
  rejected). All transports injectable (`Transports`).
- `evaluation/assertions/` package (split for the ~300-line rule;
  `_core` failure record, `turns`, `content`, `evidence`, `__init__`
  battery): turn structure (outcome + exact produced (type,version) set
  per expected turn), delegation exactness where pinned, findings
  severity ceiling per perspective (stub coverage is judge-matched by
  contract — runtime finding IDs never pinned), pinned conflict keys
  (present in the pinned synthesis version, resolved stubs absent from
  the latest), final state incl. finalized-review `po_accepted`/
  remaining-open + report formats + https signed URLs, audit rows
  (names, succeeded state, version+prompt identity, per-agent counts
  mirroring observed artifact versions), MCP evidence for `comments-*`
  scenarios (≥1 facilitator `get_story`/`list_stories` function call),
  persistence probes. `evaluate_case` never lets one group crash the run
  (exception → `group.error` failure).
- `runner.py` — default mode now executes the deterministic suite:
  `--templates t1` (cheap subset) default, `--scenario` filter,
  `--base-url/--artifact-url/--orchestration-dsn/--facilitator-dsn`
  overrides; per-case JSON artifacts (`artifacts/cases/`) + summary;
  exit 1 on any failure, 2 on setup failure. `Makefile evaluation-test`
  passes `TEMPLATES`.
- `deploy/docker-compose.yml` — compose postgres now publishes
  `127.0.0.1:${POSTGRES_HOST_PORT:-15432}:5432` (local-agents profile
  only) for the evidence reads; loopback-only like every other port.
- `requirements.in/.lock` — added `asyncpg` + path deps
  (`review-schemas`, `dataset-loader`, `ado-wire`).

Design decisions / limitations recorded:

1. **agent_runs timestamps were post-hoc → fixed in orchestration**
   (owner decision, "fix timestamps only"): every agent invocation is
   now wrapped in `timed_invoke` (`agent_clients.TimedResult` proxies
   the frozen-contract result, so call sites are unchanged) and
   `flows._record_agent_runs` / `turn_execution.record_run` persist the
   real spans. New orchestration test pins it (slow fake reviewers:
   reviewer spans overlap, synthesis starts after both, facilitator
   after synthesis). The evaluation suite asserts the designed ordering
   directly: **only the business/engineering reviewer pair may overlap;
   every other pair of spans must be strictly sequenced** — one rule
   proves fan-out, reviewer-before-synthesis, and cross-turn ordering.
2. Finding stub coverage is judge-matched per the dataset contract
   (`expected.py` docstring); only the `max_severity` ceiling is
   deterministic. Conflict C-n keys are pinned and asserted set-based.
   (evaluation-tests.md wording amendment still open — deferred with
   the owner's "fix timestamps only" decision.)
3. `conflicting`/`hidden-conflict` complete with `po_accepted:false` via
   the facilitator-gate finalize path (expected files pin it; increment 2
   sanity check unchanged).
4. MCP evidence comes from the facilitator ADK events table (adapter
   keys ADK sessions by the review session id); if the events table
   stores a differently-shaped session key the assertion will fail loudly
   and be triaged at the live gate.
5. Gotcha caught while implementing: agent_runs `agent` values are
   `business-reviewer`/`engineering-reviewer` (not `business`/
   `engineering`) — count assertions key on the full names.
6. The timestamp fix requires an orchestration image rebuild before the
   live gate (`make agents-compose-up` rebuilds it anyway).

Verification: `make evaluation-unit-test` → **82 passed**; full
orchestration suite → **207 passed / 12 skipped** (+1 span test) over the
throwaway-Postgres target; `make evaluation-test` without a stack →
clean exit 2; `git diff --check` clean; modules < 300 lines;
compileall ok.

Independent read-only review (subagent): 1 Critical / 5 Important /
6 Minor — all fixed in-session except I5 (the recorded deviation):

- **C1 fixed**: one transport/DB exception no longer aborts the suite —
  evidence queries fail → `CaseFailure`; unexpected exceptions are
  isolated per case in the runner loop (every case keeps a result +
  summary is always written).
- I1 fixed: artifact-MCP `initialize()` failure → clean exit 2.
- I2 fixed: retry budget raised to the webui's 5 attempts;
  `SESSION_LOCKED` now waits the envelope's `retry_after_seconds`.
- I3 fixed: `/health` probe requires 2xx + `status` ok/degraded body.
- I4 fixed: `make evaluation-test` builds both DSNs from
  `$POSTGRES_HOST_PORT`.
- I5 partially resolved: after the owner's "fix timestamps only"
  decision, orchestration now records real invocation spans
  (`timed_invoke`/`TimedResult`) and the suite asserts the designed
  ordering directly (only the reviewer pair may overlap). Finding-key
  presence stays judge-matched (dataset contract) — evaluation-tests.md
  wording amendment still open.
- Minors fixed: GET 503 retry, SSE multi-event decode, events-table
  discovery prefers exact `events`, agent-name normalization shared,
  `sleep` annotation, + new tests (artifact client SSE/session-header,
  runner suite filtering/isolation/summary, cross-run transport-error
  path, detail without artifact references).
- **Follow-up (owner decision "fix timestamps only")**: orchestration
  `agent_clients.timed_invoke`/`TimedResult` now wrap every agent
  invocation; `agent_runs` rows carry real spans (test-pinned: reviewer
  overlap, reviewer-before-synthesis, facilitator-after-synthesis);
  evaluation suite upgraded to the real ordering assertion (only the
  business/engineering reviewer pair may overlap). Orchestration suite
  207+12s; evaluation 82 passed.

Triage log (CODE / DATASET / PROMPT): to be filled at the live gate.

## Live t1 gate (2026-09-15, dev server; owner-approved spend; stack kept RUNNING per owner)

Run 1 (`make evaluation-test TEMPLATES=t1`, fresh compose-up): **0/10**,
two uniform failure classes:

1. `no ADK events table found` (all 10) — CODE (evaluation suite): the
   compose ADK `events` table stores payloads in **`event_data` (jsonb)**
   with the parts nested under an inner `content` object, not a `content`
   column. Fixed test-first in `db_evidence.py` (discovery accepts
   `content` or `event_data`; `_tool_call_names` descends the inner
   `content`; `_rows_to_tool_names` keyed by the discovered payload
   column — the row-key bug was found at the rerun). Evaluation suite
   86→87 passed.
2. Comments scenarios `create-session → 422` — CODE (agent adapters):
   orchestration sends the reviewer request with
   `story.model_dump(mode="json")` (ISO datetime strings); the reviewer
   adapter validated the FastAPI body in **python/strict mode**, where
   pydantic rejects datetime strings outright
   (`StrictModel(strict=True)`). `StoryComment.created_at` is the only
   datetime inside `StoryDetail`, so only comment stories hit it — which
   is why no earlier live walkthrough (stories 02/04/05/07/09/13/15, no
   comments) ever exposed it. Fixed test-first: `/invoke` now validates
   the raw body via `model_validate_json` (the synthesis + facilitator
   adapters' established pattern). agent-kit 146→148 passed; verified
   live (comment story request now reaches the model).

Gotchas:
- `agents-compose-up` recreated the compose Postgres with a fresh
  anonymous volume — the `orchestration` database (and old compose
  session history) was gone. Recreated the db + re-applied migrations
  0001–0005 through the 15432 host port before orchestration would
  start (`InvalidCatalogNameError`; orchestration has no connect retry
  at startup — restart after the db exists).
- The runner's stdout is piped through `tail` in the make target, so
  live progress is invisible until completion; per-case artifacts land
  in `tests/evaluation/artifacts/cases/` as cases finish.

Run 3 (both CODE fixes deployed, full t1): every case executes to a
terminal state and produces deterministic verdicts. **0/10 pass**;
per-case failure lists in `tests/evaluation/artifacts/cases/t1_*.json`
(run 3 artifacts; run 1/2 overwritten). Triage:

- **CODE/DATASET (open, owner decision needed)** — `turn[N].produced_artifacts`
  observes only `[(synthesis, v)]`; expected files assert the full set
  (both reviews v1 on turn 1; re-review v2 on delegation turns;
  finalized-review + reports on acceptance turns). Orchestration
  records `produced_artifacts=[synthesis_reference]` only
  (`flows.py` / `turns_flow.py` / finalization). Either the
  implementation should list every artifact the turn produced (CODE),
  or the expected contract should assert synthesis-only per turn with
  full lineage read from the artifact MCP store (DATASET/suite).
- **PROMPT-class (increment 3 loop)**:
  - synthesis `inputs` echo corruption: model echoes a wrong or
    malformed `checksum_sha256` (observed a 40-hex SHA-1-like string
    where 64-hex is required) — business-weak (2 runs), comments-benign
    (1 run); stochastic.
  - delegation not invoked where expected (business-weak,
    engineering-weak, partial-resolution, comments-clarify-business —
    all `expected engineering/business, observed none`).
  - severity calibration far above expected ceilings (blockers/majors
    in every case incl. `clean`, which expects `info`).
  - open issues never empty at acceptance (8–18 remaining everywhere).
  - conflicting/hidden-conflict: no conflicts detected in synthesis
    (`conflicts: []`) and no facilitator-gate finalize at the expected
    turn (plan flag from increment 2: confirm finalize-on-completed-
    with-po_accepted:false is actually reachable).
  - unresolvable: sessions run the full 10 turns (synthesis v6 by turn
    8) — park-at-10 not observed as expected (final state not reached).
  - mcp_evidence: no facilitator story-MCP tool calls in the ADK trace
    for comment scenarios (facilitator never reads comments →
    comments never influence the review).

Run 4 (produced-artifacts CODE fix deployed — owner decision "list all
artifacts per turn"; orchestration: flow-1 turn lists both reviews +
synthesis, delegated turns list the re-review(s) + synthesis, the
finalizing turn is stamped with finalized-review + reports by
`set_finalizing_turn_artifacts`, and the D19 catalog now filters to
synthesis-type refs; orchestration suite 207+12s, compose contract 20):
**no transport errors, no CODE-class failures remain.** Remaining
failures (4–11 per case) are all behavioral, feeding increments 2–3:

- facilitator never delegates where expected (business-weak,
  engineering-weak, partial-resolution, comments-clarify-business) but
  DOES delegate `both` on every turn in `unresolvable` (reviews v2..v9
  + synthesis each turn; expected files assume artifact-free plain
  turns) — delegation calibration is the dominant PROMPT gap.
- severity ceilings exceeded in every case (blockers/majors where
  info/minor expected, incl. `clean`).
- open issues never empty at acceptance (5–19 remaining).
- conflicting/hidden-conflict/partial-resolution: synthesis detects no
  conflicts (`conflicts: []`) and the facilitator-gate finalize never
  fires (final state stays active).
- comment scenarios: still no facilitator story-MCP tool calls (the
  facilitator never reads comments).

Increment-1 gate met: deterministic engine runs all t1 cases, produces
per-case artifacts + verdicts, CODE bucket empty.

Sessions/state: compose stack left UP (orchestration, adapters, MCP,
  postgres, webui) per owner instruction; compose Postgres carries the
  run-4 sessions (evaluation artifacts retained on disk).

## Increment 2 — dataset tuning pass (2026-09-15, dev server; owner-approved direction + spend; stack kept RUNNING)

Goal per plan §Increment 2: representativeness walk, DATASET-class repairs,
owner-reviewed ADO edits. All executed:

1. **Representativeness walk (8 tested aspects × 10 scenarios)**: every
   aspect has ≥1 strong case — reviewer correctness (weak scenarios +
   comments-complete), conflict detection (conflicting/hidden-conflict/
   partial-resolution), delegation routing (4 exact-pinned cases),
   re-review new-conflict (partial-resolution C-2, single but explicit),
   loop termination (clean/conflicting/hidden-conflict/partial), loop
   safety cap (unresolvable), persistence (runner-level probes),
   MCP-evidence (comments 43–45; **structurally sound**: facilitator has
   the story-MCP toolset + prompt guidance, and FacilitatorRequest
   carries no story text — never calling the tool is PROMPT-class).
2. **Oddity resolved (no defect)**: `conflicting`/`hidden-conflict`
   expecting `completed` + `po_accepted:false` is the designed normal
   readiness path — data-flow.md gate rule 3; example-interaction.md §5
   shows exactly this. Recorded, no change.
3. **D-a (unresolvable expected-file inconsistency)**: turns 2–9 said
   "routing NOT deterministically pinned" yet asserted
   `produced_artifacts: []`. Test-first suite changes: loader accepts
   explicit `produced_artifacts: null` = unpinned (omission still means
   pinned-empty); `assert_turn_structure` replaces the exact-set check
   with a session-wide per-type **version-continuity** assertion
   (strictly +1, no gaps/repeats); `assert_conflicts` falls back to the
   **observed** synthesis version of the first-seen turn (or first later
   synthesis) when the expected turn is unpinned. Expected file + manual
   plan updated with the unpinned note.
4. **D-b (owner: "Enrich ADO context")**: Feature "Checkout Reliability"
   (ADO id 4) had **no description** — the business reviewer's run-4
   "epic misalignment" blocker ("+8% checkout conversion", quoted from
   the epic id 2 text) was a grounded inference from an empty parent.
   Added via REST PATCH (PAT basic auth; body must be a **JSON array** of
   ops — first attempt with a single object → HTTP 400): a post-purchase
   reliability description (confirmation-email pipeline, invoice
   delivery). Story-01 (id 5) Scope gained the invoice-content sentence
   (content = exactly GET /orders/{id}; single-language, EUR; no
   branding/legal/i18n requirements). Re-exported; diff = the two text
   changes + mechanical churn (exported_at, revs 2/5, watermarks,
   comments-story Child links on the features); identifiers sanitized
   (`$ADO_ORG`/`<project-id>`). canonical-facts.md clean section records
   both enrichments. Local compose story MCP reads the bind mount —
   container restarted only to drop any cache; **no dataset-push needed
   for local runs** (dev-mode runs in increment 4 will need it).
5. **Run 5** (`make evaluation-test TEMPLATES=t1`, owner-approved spend):
   **0/10 pass, DATASET bucket EMPTY** — increment-2 gate met.
   - **t1/engineering-weak: 0 failures — first fully passing case**
     (engineering-only delegation with extra context, artifacts, severity
     within ceiling, finalize, reports).
   - **t1/unresolvable: 11 → 3 failures** — all artifact-pinning failures
     gone; park-at-10, turn outcomes, parked final state pass.
   - Remaining failures everywhere are PROMPT-class (increment 3):
     delegation routing (single-side expected, `both`/none observed;
     conflicting/hidden-conflict turn-2 delegation instead of
     conversational resolution), severity ceilings (blockers in every
     case), open issues never empty at acceptance (7–19), synthesis
     conflict detection (`conflicts: []` everywhere incl. C-1/C-2),
     facilitator story-MCP tool calls on comment scenarios.
6. Verification: dataset **37 passed** (+1 null-semantics loader test);
   evaluation **90 passed** (+3: unpinned tolerance, version-gap failure,
   conflict capture-fallback); `git diff --check` clean.

Sessions/state: compose stack left UP per owner instruction; run-5
sessions in the compose Postgres; run-5 artifacts in
`tests/evaluation/artifacts/cases/` (run-4 overwritten).

## Session note — dev DB resumed (2026-09-15)

Owner requested the dev environment usable: Cloud SQL resumed
(`make db-resume`; the `make` call itself blocks past the operation —
poll `gcloud sql instances describe … --format='value(state)'`; ~6 min
to RUNNABLE). First orchestration requests after resume hit the known
Runbook 14 cold-start race (startup-probe asyncpg
ConnectionDoesNotExistError → 503/500); cleared on retry with no
intervention. Live again: `/api/v1/stories` 200 through the public
domain.

Gotchas recorded:
- `make db-status`/`db-resume` on the dev server need
  `CLOUDSDK_CORE_PROJECT=$PROJECT_ID` (after `source
  infra/envs/home.env`) — gcloud has no `core/project` configured on
  this machine.
- **Standing instruction from the owner: the DB stays RUNNING — do not
  pause it until explicitly asked.**

## Increment 3 — judged stage + prompt tuning loop (2026-09-16, dev server; IN PROGRESS)

### Code (all test-first; evaluation 90 → 104 unit tests)

- `evaluation/judge_stage.py` — builds the judge case input (capture +
  expected file as ground truth; `prompt_sha256`/`judge_model` injected,
  echoed per increment-0 identity rule) and runs exactly one judge call
  via `judge_client.judge_case`; `judge_smoke` moved here from runner
  (file-size rule). `judge_client` gained the `JudgeCaseFn` protocol for
  injection.
- `evaluation/trend.py` — every run appends one timestamped entry to
  `artifacts/trend.json` and re-renders `trend.md` (per-run deterministic
  + judged pass rates, per-case judge scores, failure lists).
- `runner.py` — `--judge` (one judge call per **deterministic-passing**
  case only — cost control + gate order), `--smoke` (t1 deterministic
  suite + judge only on `clean` — the designed pipeline-gate smoke set),
  `--label`; judge-stage errors mark the case failed; live-transport
  build failure (missing `GOOGLE_CLOUD_PROJECT`) = clean exit 2.
- `Makefile` — `evaluation-test` gains `JUDGE=1`; `evaluation-smoke` is
  now the smoke set above (the old canned single-call smoke remains
  available as `python -m evaluation.runner --judge-smoke`).
- **Delegation assertion re-based on executed evidence** (CODE-class
  suite fix, root-caused at run 8): `TurnRecord.delegation` is by design
  (schemas.md §FacilitatorTurnOutput, Item G/D21) the *post-delegation
  summary* output — whose own invocation is a next-turn intent — so the
  old assertion read the wrong field and reported `expected business,
  observed none` on every correctly-delegated turn.
  `assert_delegation` now derives routing from what *executed*: review
  versions ≥ 2 produced that turn (single side / both / none), reuse =
  synthesis-only later turn, extra-context presence from the re-review's
  `based_on_extra_context`; `open_issues` stays on the recorded final
  output (gate-authoritative). Matches evaluation-tests.md "selected
  reviewer routing exactly matches the scripted PO clarification".
  Recorded as D13 amendment 3 context in local-decisions (suite-side
  reading; expected files unchanged).

### Model bump (D13 amendment 2, owner-approved experiment)

Run 6 (flash, prompt round 1) showed severity/delegation/open-issues
unchanged after targeted prompt edits while the MCP fix landed —
flash's instruction-following was the plateau. Owner chose "try pro on
reviewers + facilitator": `agents/{business-reviewer,
engineering-reviewer,facilitator}/config.yaml` → `gemini-2.5-pro`
(synthesis stays flash). Run 8 (pro, same prompts): large improvement
(clean open issues 12→6; conflicts detected + resolved on `conflicting`;
business-weak delegation — which pro had done correctly all along, see
the assertion fix above — passes).

### Prompt tuning rounds (all in `prompts/*.md`, evidence = run N artifacts)

- Round 1 (run 6): reviewer severity-calibration rubric; facilitator
  single-side-default delegation, no-re-invocation-without-new-facts,
  open-issues convergence, mandatory `get_story` on the opening turn.
  Landed: **MCP evidence fixed** (facilitator story-MCP tool calls now
  present on comment scenarios).
- Round 2 (run 7): reviewer scope-echo/grounding rules; facilitator
  no-conversational-resolution + minor/info never open. Marginal.
- Round 5 (run 9): worked scope-boundary example; operational-territory
  rule; decision-vs-new-facts distinction; acceptance-settles rule.
  `conflicting` turn 2 now routes correctly (no re-review on a decision).
- Round 6 (run 10): enumerated-failure-paths rule; decision resolves
  every resting finding.
- Round 7 (run 11): re-review-must-resolve-answered-findings;
  platform-facility rule; pre-reply re-grade self-check; summary-turn
  resolution discipline.

Latest subset state (run 11, clean/business-weak/conflicting):
- **clean**: 4 failures — engineering severity (E-1/E-2 major stochastic
  across runs: order-API fetch failure / audit-log+alerting deps) +
  downstream open issues.
- **business-weak**: 2 failures — engineering down to 2 minors (ceiling
  info) + 2 remaining open at final.
- **conflicting**: 4 failures — turn-2 routing correct, but 3 issues
  still open at the decision turn (facilitator resolves the ones it
  acknowledges, keeps definitional majors open) → no readiness → no
  finalize.

Sessions/state: compose stack UP with pro reviewers+facilitator;
run-11 artifacts in `tests/evaluation/artifacts/cases/` (trend.json has
runs 7–11 labels); judge stage wired but **not yet exercised live** (no
deterministic-passing case yet).

### Increment 3, part 2 — prompt rounds 8–10 + story-01 enrichment + first full-suite pass (2026-09-16, dev server)

All runs owner-approved spend, compose stack, pro reviewers + facilitator
(flash synthesis), temperature 0.0 throughout.

#### Story-01 ADO enrichment (D-b pattern, owner-approved)

Persistent minor "email delivery failures other than hard bounces are
undefined" (AC3) survived 3 prompt rules + a worked example — pro believes
it a genuine story gap. Owner chose data-level fix: PATCH ADO id 5 → rev 6,
Scope sentence added ("email delivery failures other than hard bounces
follow the existing email platform's standard delivery-failure handling …
out of scope"). Re-exported (45 stories + 3 context; diff = story-01
description + mechanical churn); canonical-facts clean section records it;
story MCP container restarted (bind mount). Enrichment cleared the
open-issues cluster on clean.

#### Prompt changes (rounds 8–10, all in prompts/*.md)

- **engineering-reviewer.md**: scope-by-reference rule (referenced
  endpoint = the specification, its schema/failures info at most);
  implementation-territory rule (idempotency/concurrency/identifier
  sourcing/debug storage/info); general-failure-path-covers-subcases rule
  with worked examples (rendering failure ⊃ fetch failure; hard-bounce
  retry settles that path); re-grade gate extended from major-only to
  minor+; SLA-feasibility → risks; **grounding section consolidated from
  a ~25-bullet wall into an ordered 3-step severity decision procedure**
  (story-settles → implementation-territory → real-gap gate) + few-shot
  calibration example ("well-specified story ⇒ info-only list").
- **business-reviewer.md**: report-rendering details (filename,
  formatting) info at most; few-shot calibration example.
- **synthesis.md**: conflict materiality (minor/info gap-vs-positive-
  summary asymmetry is not a conflict; risks/questions are observations,
  never conflict sides); no self-minted questions_for_po from minor/info
  findings; pre-emit gates 1–2.
- **facilitator.md**: decision-resolves-definitional-findings (definition
  now exists; detail inside the decided design = implementation
  territory, never re-asked); acceptance-turn open_issues always empty;
  opening-turn filter (only major/blocker + needs_po_clarification may be
  open; minor/info resolved same turn; synthesis questions on minor/info
  findings not relayed).

#### Gotcha: prompt `{id}` braces vs ADK templating

Adding "`GET /orders/{id}`" verbatim to a prompt broke the reviewer with
`model call failed: 'Context variable not found: id'` (503,
reproducible): ADK substitutes `{identifier}` placeholders in agent
instructions against session state. Multi-char/quoted braces (e.g. JSON
examples in facilitator prompt) don't match. Prompt text must avoid
single-identifier braces.

#### Runs 12–23 (trend.json labels run-12…run-23-full-t1)

- Runs 12–19 (clean only): each round fixed its targeted cluster; every
  run one *different* rotating stochastic blip remained (new minor/major
  framings: idempotency, large orders, SLA feasibility, hard-bounce
  detection mechanism, PDF filename, invoice-content legal compliance —
  the last contradicting both story text and its prompt's worked
  example). Rounds 9–10 (consolidated procedure + few-shot calibration)
  produced the first fully green clean severity list (run 22 engineering:
  info-only, calibration followed exactly).
- Run 20: post-enrichment — open-issues green; new minors per reviewer.
- Run 22: severity green; synthesis minted C-1 from info-vs-summary
  (pre-emit gates added after).
- **Run 23 (full t1, 1/10): t1/clean PASSED** — first deterministic
  pass of a non-trivially-green case in the full suite. Regressions
  elsewhere:
  - comments-benign/clarify-business/complete-engineering: blocker/major
    escalations (ceiling info/major) + open issues — the story-01-targeted
    calibration did not generalize to comments stories.
  - engineering-weak turn 2: invoke `both` instead of `engineering`
    (single-side routing regression).
  - partial-resolution turn 3: invoke `both` + extra_context instead of
    `none` (decision-vs-new-facts regression); C-1/C-2 unresolved in
    synthesis v3.
  - unresolvable: blockers over major ceiling; synthesis v2 conflicts []
    (C-1 expected present).
  - hidden-conflict: 422 DELEGATION_VALIDATION — facilitator re-listed
    C-1 on open_issues without a `reopened` disposition (identifier
    lifecycle rule violated; 2 corrective re-prompts exhausted).

#### Verification

Dataset 37 passed; evaluation unit 104 passed; `git diff --check` clean.
No code changed this part (prompt + dataset only; dataset-test green).

Sessions/state: compose stack UP (run-23 prompts baked); run-23 artifacts
in `tests/evaluation/artifacts/cases/`; trend.json has runs 12–23.
Judge stage still not exercised live (only clean passed so far).

### Increment 3, part 3 — comments-story AC repair, D30 arc adaptation, prompt round 11 (2026-09-16, dev server; owner-approved)

Triage of run 23 produced two structural findings (both owner decisions,
recorded as **D30**):

1. **Comments cluster = DATASET, not prompts**: ADO 57/58/59 (stories
   43–45) were authored without the acceptance criteria
   `dataset/comments-stories-spec.md` defines (exported
   `acceptance_criteria: []`). The blockers ("unbuildable, no AC") were
   grounded in missing data. Fixed: REST PATCH (PAT basic auth, JSON-array
   op body, `Microsoft.VSTS.Common.AcceptanceCriteria`) with the spec
   criteria verbatim in Given/when/then HTML — revs 5/5/6; re-exported
   (45+3, diff = the three AC fields + mechanical churn incl.
   `commentVersionRef`/`System.History` dropping — comment payloads come
   from the comments API and are unaffected; loader tests green); story
   MCP container restarted; verified live via `get_story` (3/2/2 ACs).
2. **Gate-finalize vs scripted acceptance (business-weak run-23 409)**:
   round-10 convergence empties `open_issues` on the post-delegation
   summary turn → the designed readiness gate (data-flow §2 rule 3)
   finalizes with `po_accepted=false` → the trailing scripted acceptance
   turn 409s (SESSION_READ_ONLY; orchestration logs confirm finalize at
   turn 2, second POST new correlation id — not an idempotency defect).
   Adapted per D30: business-weak, engineering-weak,
   comments-clarify-business expected files + manual plans drop the
   acceptance step; turn 2 = finalize turn (re-review v2 + synthesis v2 +
   finalized-review + report stamps; confirmed against the live
   gate-finalized turn record). partial-resolution already modeled this
   shape. Flow 3 (acceptance) stays covered by clean +
   comments-benign/complete-engineering.

Prompt round 11 (PROMPT-class clusters): both reviewers — `blocker`
refined (vague/incomplete = majors, no escalation by count; targets
unresolvable); business — technical mechanisms are engineering territory
(`info` at most; targets engineering-weak B-1); facilitator —
finding-ownership routing (`B-*`/`E-*` decides the side; targets
engineering-weak turn-2 `both`), directives-to-incorporate are decisions
(`invoke=none`; targets partial-resolution turn 3), pre-emit
identifier-lifecycle self-check (targets hidden-conflict 422); synthesis
— pre-emit gate 3, carried-over conflicts re-verified against the latest
review per side (targets stale C-2).

Verification: dataset 37 passed, evaluation 104 passed, story MCP serves
the new ACs, `git diff --check` clean. No application code changed.

### Increment 3, part 4 — run 24 (round-11 validation) + round 12 (2026-09-16, dev server; owner-approved spend)

Run 24 (full t1, round-11 prompts baked via agents-compose-up; executed
as one full pass — killed at ~45 min by the bg-job runtime cap after
clean/business-weak/comments-benign — then per-scenario runner calls
`--scenario` for the rest, plus conflicting/comments-clarify retries;
trend labels run-24-* / run-24b-*). **Result: 0/10, but every case
converged materially** (open issues 4–19 → 1–3; blockers eliminated
except one stochastic unresolvable E-1; routing single-side correct in
business-weak/comments-clarify):

- **AC restoration worked**: comments cases dropped from blockers/majors
  to 0–3 minors (residuals: engineering minors on adjacent failure paths
  / dashboard testability; business minor on failed-split UX).
- **Remaining failure shapes** (round-12 targets):
  1. **Summary/final turns keep 1–3 issues open instead of emptying**
     (business-weak 3, comments-clarify 1–2, conflicting 3,
     partial-resolution 3, engineering-weak 2) — dominant cluster.
     Sub-shapes: (a) re-reviews mint NEW majors from the PO-supplied
     metric's enabling infrastructure (business-weak B-1 "analytics",
     comments-clarify B-1); (b) facilitator acknowledges a decision but
     keeps the decided findings open ("we've noted that, but the key
     questions remain open" — conflicting, partial-resolution).
  2. **Synthesis dropped pinned conflicts entirely** in several runs
     (partial-resolution C-1/C-2 absent even at v1/v2; hidden-conflict
     C-1 absent at v1; unresolvable C-1 absent) — suspected round-11
     gate-3 over-suppression; hidden-conflict reviewers also escalated
     majors on the individually-positive story.
  3. Stochastic (documented, single occurrence each): comments-clarify
     create 422 VALIDATION_ERROR — synthesis echo checksum malformed
     (known run-3 echo-corruption class, flash); conflicting create 422
     facilitator opening-turn validation (parked session); clean E-1
     minor blip after 3 green runs; unresolvable single blocker.

Round 12 (prompts only, landed after run 24): reviewers — re-review
scope discipline (re-review resolves, does not open a new front;
enabling infrastructure for PO-supplied metrics = info); facilitator —
binding worked example of the decision-enforcement failure shape
("noted but remains open" forbidden; conflicting/partial-resolution
messages spelled out); synthesis — gate 3 applies only to
previously-emitted conflicts and never suppresses detection.

Verification: dataset 37, evaluation 104, `git diff --check` clean.
Gotchas: bg job runtime cap ≈45 min (run t1 in chunks of ≤4 cases via
`python -m evaluation.runner --scenario`, not make); Makefile
`evaluation-test` has no SCENARIO passthrough; local probe session
`sess-5bad9c9b…` left active (creator x-user-id not persisted — the
known increment-7 abandon limitation).

Judge still not exercised (no deterministic pass in run 24).

### Increment 3, part 5 — run 25 (round-12 validation): regression found, isolated to round-12 reviewer edits, reverted to round-12b (2026-09-17, dev server; owner-approved spend)

Round-12 prompts baked via `agents-compose-up` (image md5 verified
against repo `prompts/`). Run 25 executed per-scenario
(`python -m evaluation.runner --scenario`, labels `run-25-*`) in two
chunks; chunk 3 (partial-resolution, unresolvable) was **not run** —
chunk 2 evidence made the diagnosis clear first.

**Result: 0/9 — a systematic regression, not the run-24 residuals:**

- **Chunk 1** (clean, business-weak, comments-benign,
  comments-clarify-business): 0/4. Clean failed with minted v1 majors
  (B-1 formal-invoice legal info, E-1 cancelled-order hypothetical path,
  E-2 zero-total) — direct violations of binding severity rules that
  held in three green runs on rounds 10–11.
- **Chunk 2** (clean rerun + comments-complete-engineering, conflicting,
  engineering-weak, hidden-conflict): 0/5. Clean rerun also failed
  (2 open, E-1/E-2 minors) — clean now failed twice consecutively vs
  3 greens + 1 stochastic blip before; not stochastic-only. Major-minting
  worse than run 24 everywhere (engineering-weak B-1/B-2 majors;
  hidden-conflict 3+3 majors); synthesis still dropped pinned conflicts
  (conflicting C-1, hidden-conflict C-1); facilitator still kept decided
  issues open.

**Diagnosis (A/B, owner-approved):** working-tree reviewers reverted to
round-11 (`git show 27fa8ff^:prompts/*`), adapters rebuilt, one clean
run — **PASS** (`run-25-clean-r11ab`). Causation confirmed: the
round-12 reviewer edits regressed severity calibration. The v1-time
failure point rules out the re-review-scope text; prime suspect is the
shared severity-calibration rewording (the `blocker` disambiguation
shifted the model's notion of what a `major` is). Facilitator
(decision-enforcement worked example) and synthesis (gate-3 scoping)
edits were not implicated at v1.

**Round 12b (validated configuration):** reviewers at round-11,
facilitator + synthesis at round-12 → clean **PASS**
(`run-25-clean-r12b`). This is the committed state going forward (D31).
Reviewer re-review-scope discipline to be re-attempted later as a
smaller additive edit without the severity rewording, tested on
business-weak / comments-clarify-business.

Verification: trend labels `run-25-clean`, `-business-weak`,
`-comments-benign`, `-comments-clarify-business`, `-clean2`,
`-comments-complete-engineering`, `-conflicting`, `-engineering-weak`,
`-hidden-conflict`, `-clean-r11ab`, `-clean-r12b`; per-case artifacts
under `tests/evaluation/artifacts/cases/` (last run per case wins;
trend + this entry carry the history). Judge still not exercised
(run-25 clean passes came from un-labeled chunks; next deterministic
suite pass should add `JUDGE=1`).

Gotchas: (1) per-case artifact JSONs are overwritten per run — the
trend file is the durable per-run record; (2) A/B rebuild takes ~1 min
per adapter image, no stack restart side effects observed; (3) GCP live
agents predate round 12 entirely (facilitator `747d9d1`, others
`7d1b9bd`) — see Runbook 14 increment 7; round-12b must be deployed
there (this session, part 6).

### Increment 3, part 6 — GCP round-12b/12c deploy, AE corrective-loop gap found, live rollback to facilitator-747d9d1 (2026-09-17, dev server; owner-approved "commit, push and redeploy" + "rollback live now")

1. **Deploy round-12b** (`6a73636`, pushed): four new engines
   `business-reviewer-6a73636` (`6967464447728156672`),
   `engineering-reviewer-6a73636` (`5962317305894404096`),
   `synthesis-6a73636` (`1202856924693921792`),
   `facilitator-6a73636` (`6618435476606943232`); all SMOKE PASS;
   orchestration → revision `orchestration-00034-zxf` (env verified).
2. **Live session creation 422** (DELEGATION_VALIDATION, opening turn):
   `the opening facilitator turn must emit invoke=none and no resolution
   updates` — 4/4 deterministic. Meanwhile the local compose stack passed
   the same flow.
3. **Found and fixed a stale live dataset**: the GCS story dataset bucket
   was uploaded 2026-09-09 (pre story-01 rev-6 enrichment, pre D30
   comments ACs). `gsutil -m rsync -r -c dataset/stories
   gs://…-story-dataset/stories` (48 objects) + `mcp-story` rolled to a
   new revision of the same image (`mcp-story-00007-vbb`; the mock source
   loads the dataset at startup). Live story-01 description then matched
   local (1041 chars). Necessary hygiene, but NOT the 422 cause.
4. **Root cause (probe-verified)**: replaying the exact opening-turn
   message against the AE engine reproduces `invoke=none` + 5 opening-turn
   `resolutions` (info findings "resolved"); the local adapter on the same
   message emits none. The **AE runtime path
   (`build_facilitator_root_agent`) exposes the raw LlmAgent — it has no
   `validate_turn_output` / `turn_with_corrections` corrective loop** that
   the local HTTP adapter applies. The round-12 facilitator prompt's
   resolve-info-findings rule makes the model resolve at turn 1; the
   round-12c prompt override ("never on turn 1", `5452be1`, committed +
   deployed as `facilitator-5452be1` = engine `732230763633704960`,
   SMOKE PASS) binds locally but is ignored on the AE serving path — the
   422 persisted.
5. **Owner decision — rollback live**: orchestration pointer back to
   `facilitator-747d9d1` (`6251392106976247808`) → revision
   `orchestration-00036-jnp`; live flow-1 create on story-01 → **201**
   (`sess-135fa2a8…`, left active; creator user id persisted this time).
   Live is a MIXED stack: reviewers/synthesis `6a73636` (round-12b) +
   facilitator `747d9d1` (pre-round-12) — not the locally-validated
   round-12b combo (D32).

Open design work (D32): bring turn-context validation + corrective
re-prompting to the AE runtime (candidate (a): deterministic turn-1
boundary repair via model callback + telemetry; candidate (b): port the
full corrective loop as a custom agent) — decision with the owner; until
then the facilitator round-12 prompt improvements stay local-only.
Probe tooling: `tmp/probe_facilitator.py` (message render from a stored
capture), `tmp/probe_ae_facilitator.py` (AE impersonated replay),
`tmp/probe_local_facilitator.py` (local adapter same-message A/B).

Verification: engine env on revisions 00034/00035/00036 verified via
Cloud Run v2 API; live 201 on the public domain; local compose clean
PASS with round-12c prompt. Gotchas: (1) `gcloud run services deploy`
does not exist in this gcloud — use `update` (v1 surface); (2) the GCS
dataset bucket does not auto-sync with `dataset/` — any dataset repair
must re-run the rsync + mcp-story revision roll; (3) smoke.py's
facilitator opening turn uses a synthetic story — it does NOT guard the
real-story opening-turn contract.

### Increment 3, part 7 — D34 deployed, live opening-turn contract verified, run-26 t1 chunk + documented clean rerun (2026-09-17, dev server; owner-approved "continue with deploy and testing")

1. **Facilitator engine** (D34 prompt, HEAD `4c81133`): deployed as
   `facilitator-4c81133` = engine `2601224608992460800`; smoke.py PASS
   (`invoke=none`). Retained (D5 prune list grows by one).
2. **Orchestration** (corrective loop): image
   `20260917-2039-4c81133` → revision `orchestration-00037-m4c`; env
   verified via Cloud Run v2 API (facilitator pointer =
   `2601224608992460800` / `facilitator-4c81133`); `/health` ok (report
   cold-start blip on first probe — transient, min-instances 0).
   Gotcha update: `gcloud run deploy` worked this time (runbook part-6
   "use update" note was gcloud-version-specific).
3. **AE probe** (`tmp/probe_ae_facilitator.py`, impersonated
   sa-orchestration): opening-turn message replay (5121 chars) → raw reply
   shows exactly the D34 P1 fence: `invoke=none` + 5 one-line
   `resolved` resolutions for the info/minor findings. Stale probe nit:
   `tmp/probe_facilitator.py`'s summary print uses dict access on
   pydantic models (`'Finding' object is not subscriptable`) — message
   render itself is fine.
4. **Live flow-1 gate**: `POST /api/v1/sessions` story-01 via the public
   domain → **201** (`sess-06fdb260-cc0d-544a-af17-8582c42bd749`;
   user id in `/tmp/d34-verify-user.txt`; left active). Opening turn:
   `invoke=none`, `readiness=ready`, clean reply. This is the exact
   request that deterministically 422'd pre-D34 — the mixed live stack is
   now converged on round-12b+P1 (all four engines current).
   Operator gotcha: POST /sessions also requires `Idempotency-Key`
   (UUID v4); a missing header surfaces as the generic
   VALIDATION_ERROR "malformed request" 422 — easy to misread as the
   old delegation 422.
5. **Local stack rebuilt** (`make agents-compose-up`) to HEAD so compose
   matches the deployed images; `/health` ok on 127.0.0.1:8130.
6. **run-26 t1 (round-12b+P1, labeled run-26-p1)**: chunk A
   (clean, business-weak, engineering-weak, comments-benign) **0/4** —
   all four on the known reviewer severity-drift class: e.g. clean's
   business reviewer minted B-1 `major` ("Potential for non-compliant
   invoice content") + synthesis promoted C-1
   (`needs_po_clarification`); the facilitator then behaved per the D34
   fence (kept only B-1/C-1 open at turn 1, info findings resolved). No
   D34-specific failure; no 422. Owner decision: rerun clean once, stop.
   **Clean rerun PASS** (label `run26-p1-rerun`) — drift confirmed as
   stochastic per the plan's documented-rerun practice; failing-run
   evidence in `/tmp/run26-chunkA.log` + trend.md, passing capture in
   `cases/t1_clean.json`.
7. **run-26 remainder (owner-approved "test the rest of the stories,
   only one template" — t2–t6 untouched)**: chunks B+C
   (comments-clarify-business, comments-complete-engineering,
   conflicting, hidden-conflict, partial-resolution, unresolvable) —
   **0/6**, full-suite run-26 = 0/10 (+ the documented clean rerun
   PASS). All failures the reviewer over-severization class, at a worse
   amplitude than run-25: hidden-conflict minted B-1/B-2 `major` +
   E-1 `blocker` (+ spurious `both` delegation with extra_context);
   unresolvable minted every finding `blocker` over a `major` ceiling
   and mis-kinded C-1 as `needs_po_clarification` (expected
   `recurring`); partial-resolution left 6 issues open with C-1/C-2
   unresolved in synthesis v3. No D34-specific failure, no 422.
   Chunk logs: `/tmp/run26-chunkB.log`, `/tmp/run26-chunkC.log`.
   Conclusion: reviewer severity calibration is now the single blocker
   to a green suite (tuning session next).

### Increment 3, part 8 — D35: triage, story enrichments, prompt round 13, reviewer severity fence + suite tolerance (2026-09-18, dev server; owner-approved "proceed looks good" / "both")

1. **Run-26 triage** (owner: "explain, then triage"): extracted every
   minted finding from the run-26 case artifacts
   (`/tmp/triage-findings.txt`) vs the expected files. Verdict: 3
   clear-cut story-edit candidates, 2 secondary, 4 unfixable-by-story
   (stochastic mint, cross-perspective duplication, re-review
   re-listing, designed-contradiction inflation), 1 expected-file
   question (unresolvable blockers arguably correct).
2. **Dataset corrections** (owner decisions: raise unresolvable ceiling
   to `blocker`; C-1 kind `recurring` → `needs_po_clarification` —
   `recurring` was structurally unsatisfiable, the assertion maps
   observed kinds to needs_po_clarification/resolvable only).
3. **Five ADO enrichments (D-b pattern)**: ids 10 (explicit no-success-
   metric + default button presentation), 17 (step budget: one
   interaction after page load), 57/58/59 (comment #4 each: order-API
   failure out of scope; gift-card remove + existing failure UX; 4xx
   terminal → DLQ). REST PATCH (PAT basic auth, JSON-patch array body,
   **Content-Type `application/json-patch+json`** — plain
   `application/json` → HTTP 400); comments via POST
   `wit/workItems/{id}/comments?api-version=7.1-preview.4` (plain 7.1 →
   preview-version error). ids 507000–507002; revs 5/3. Re-exported
   (45+3); diff = the five changes + mechanical churn; loader tests 37
   passed; recorded in canonical-facts.md + comments-stories-spec.md.
4. **Prompt round 13**: business-reviewer perspective-discipline rule
   (technical behavior = engineering territory, ≤ info from business
   view) + re-review severity discipline (re-list unchanged only if
   context left subject entirely untouched); engineering-reviewer
   mirrored re-review rule.
5. **Run 27** (round 13 + enriched stories, label run-27-*): 0/10 but
   amplitude dropped broadly (clean major→minor; engineering-weak B
   major→minor; unresolvable down to 1 assertion; comments-complete-
   engineering down to 1). Proof of the whack-a-mole conclusion: every
   fix kills one mint and a different one appears; partial-resolution
   drifted the *other* way (designed E-1 blocker came out major → C-1
   never formed). Owner decision: **D35 = hard fence + suite tolerance
   (both)**.
6. **D35 implementation**: design added to `docs/design/data-flow.md`
   (§Reviewer output fence) + `docs/quality/evaluation-tests.md`
   (§severity tolerance); decision recorded in local-decisions.md.
   - `orchestration/orchestration/reviewer_output_fence.py`: pure
     deterministic fence — Rule 1 scope-settlement drop (finding
     overlapping ≥ 0.35 overlap-coefficient with a settling clause:
     markers "out of scope", "no additional", "exactly", …), Rule 2
     re-review clamp (match ≥ 0.35 to a previous finding + ≥ 0.20
     overlap with extra context → one level below previous severity;
     previous info → drop). Thresholds empirically calibrated on run-27
     captures (plain Jaccard 0.3 does not fire; overlap coefficient
     does; context threshold 0.25→0.20 documented deviation). Wired at
     both choke points (`flows._fan_out_reviewers`, `turn_execution`
     re-review); structured `reviewer_output_fence` events; persisted
     artifact = post-fence report.
   - Runner `--tolerance minor-over-info`: pure minor-over-info ceiling
     failures reclassified to visible `tolerated` entries (case
     artifact, summary, trend); default strict.
   - Bug found live and fixed: `_fence_result` on the re-review path
     hit `TimedResult` wrappers → 500 (`dataclasses.replace` got
     `report` kwarg); fix rebuilds the inner result; regression test
     added. Capture-regression tests re-pinned to committed fixtures
     (`orchestration/tests/fixtures/d35_*.json`) because artifacts/
     captures are overwritten every run.
   - Verification: `make orchestration-test` **231 passed** (+13),
     evaluation unit tests **113 passed** (+9), dataset loader 37.
7. **Run 28** (D35 fence + tolerance, label run-28-*): **2/10 — t1/clean
   and t1/comments-benign PASS** (first time; clean had never passed
   outside a rerun). Remaining 8, by class:
   - *synthesis conflict emission* (unresolvable 1 fail: C-1 missing in
     v2; partial-resolution C-1/C-2 never emitted; hidden-conflict C-1
     missing v1) — synthesis gate/detection variance, NOT severity.
   - *routing drift*: engineering-weak invoke both; comments-clarify
     invoke none (finalized without the designed delegation);
     hidden-conflict invoke engineering.
   - *unfenced minor keeps issues open*: comments-complete-engineering
     (severity tolerated but the minor's open issue blocked the
     readiness finalize).
   - hidden-conflict severity inflation persists (blocker/major on the
     designed contradiction — correctly NOT fenced: the story must stay
     contradictory; this remains prompt/calibration territory).
   Chunk evidence: trend.md run-28-* entries; runner output in session.
