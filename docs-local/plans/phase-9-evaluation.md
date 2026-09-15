# Phase 9 — Evaluation suite & story/prompt tuning plan

## Objective

Implement the **agent evaluation tests** requirement from
`docs/quality/evaluation-tests.md`: a runnable evaluation suite over the mock
dataset (deterministic assertions + fixed-threshold LLM judge), executed
locally (compose stack, real agents + Vertex) and against the deployed dev
environment — then use it as the driver for a **tuning loop over the dataset
stories and the agent prompts** until every required case passes.

**Owner scope decisions for this phase (to be recorded as D29):**

1. **Demo postponed** — the live-demo step of Phase 9 does not happen until the
   whole evaluation suite passes. This phase ends at "all required dataset
   cases pass locally and against dev; coverage table updated". The demo
   becomes the opening item of the next phase.
2. **Story tuning is in scope**: the existing 45-case matrix (42 + 3
   t1-only comment scenarios) is iterated — stories, expected files, and
   manual plans — so the dataset better represents all scenarios the
   evaluation is supposed to prove (reviewer correctness, conflict detection,
   delegation routing, re-review synthesis, loop termination/cap,
   persistence, agent-driven MCP use).
3. **Agent prompt tuning is in scope**: failures attributable to prompt
   wording (not orchestration logic) are fixed in `prompts/*.md` and
   re-proven by the suite. Prompt changes are exactly the designed trigger
   for running the full evaluation gate, so this loop is self-consistent.

Consistent with D24-1: **no CI/CD** — the designed `pipelines/evaluation.yml`
stays a documented intent; the runner is a make target run locally
(`make evaluation-test`), same as `orchestration-integration-test`.

Per development-plan.md Phase 9 exit criteria (amended by D29-1):
judge config + `prompts/judge.md`; expected-file test runner with
deterministic assertions; run modes (local compose preferred); all required
dataset cases pass (deterministic + judged) locally and against dev;
requirements-coverage.md updated with evidence. Demo: deferred.

Cost: Vertex AI tokens (agents + judge) across cases — the full required set
is ~45 cases × (flow turns + 1 judge call each); the smoke set is one judged
case. Cloud SQL must be resumed for the dev run; pause afterward.

## Preconditions

- Phase 8 complete and closed (Runbook 14); Cloud SQL currently STOPPED —
  resume only for the dev-mode runs.
- Local compose stack pattern proven (`make agents-compose-up`,
  `orchestration-integration-test`); `tests/contract` exists as the structural
  home for new suites.
- `JudgeResult` schema already designed (`docs/design/schemas.md` §JudgeResult)
  — lives in review-schemas if needed as a typed artifact, or stays
  suite-local per schemas.md; settle at increment 1.
- Dataset matrix exported from ADO (ids 5–59). **Tuning stories means editing
  the ADO work items and re-exporting** (`dataset/tools/export_ado.py`,
  `set -a; source infra/envs/ado.env; set +a`) — not hand-editing
  `dataset/stories/*.json` — plus regenerating `dataset/expected/*` and the
  corresponding manual plans. Export diff reviewed before commit.

## Deliverables

- `prompts/judge.md` — judge prompt per evaluation-tests.md (five dimensions,
  0–4, blocker severity, no shared state with agents).
- `tests/evaluation/` — runner package:
  - `config.yaml` — judge config (model `gemini-2.5-pro`, temperature 0, one
    candidate, `judge.md` SHA-256); records publisher model/version metadata.
  - Case runner: loads `dataset/expected/<scenario>.json`, drives the
    orchestration API (po_script turns, acceptance, finalize), captures typed
    outputs + traces.
  - Deterministic assertions per evaluation-tests.md (finding keys set-based,
    parallel overlap, caller/ordering, deployment IDs — local-mode equivalent:
    distinct adapter identities, routing exactness, lineage versions, MCP
    tool-call evidence, persistence restore/reject, gate/turn-cap/state).
  - Judge client: one call per passed case, ≤1 identical retry on transient
    transport failure, invalid structured output = fail, no best-of-N.
  - Typed results + traces saved as artifacts (JSON) per run; aggregate
    trend report; non-zero exit on any failure.
- `make evaluation-test` (+ `evaluation-smoke`) targets; compose profile
  already exists.
- Dataset tuning: revised stories in ADO + re-export; revised
  `dataset/expected/*` + manual plans; loader tests still pass
  (`make dataset-test`).
- Prompt tuning: revised `prompts/*.md` where evaluation evidence warrants;
  mirrored AE deploy label changes noted for the eventual redeploy.
- `docs/quality/requirements-coverage.md` — "Agents evaluation tests
  implemented" row → implemented/verified with evidence; coverage rows for
  session management, session context, MCP-on-Cloud Run that cite
  "integration tests" upgraded where the suite now provides the evidence.
- Runbook 15 (evaluation runs: local + dev evidence, gotchas).

## Case matrix (from `dataset/expected/*.json`, verified 2026-09-16)

10 scenarios; `clean`, `comments-benign`, `comments-complete-engineering` are
single-PO-step accepts; `business-weak`/`engineering-weak`/
`comments-clarify-business`/`partial-resolution` carry a turn-2 delegation
(business or engineering, extra-context, no reuse); `conflicting`/
`hidden-conflict` resolve by PO message; `unresolvable` is the 10-turn park
arc. Comment scenarios are the MCP-evidence cases (facilitator must read
comments via the story MCP during the opening turn). Expected files pin:
`expected_turns` (outcome, state, artifacts+versions, delegation),
`expected_findings` (semantic keys B-*/E-*, min_severity, appears_in_version,
resolved_at_turn), `expected_conflicts`, `expected_final`, `invariance`.

## Increments — detailed

### Increment 0 — Judge + runner skeleton (local, minimal Vertex spend)

Goal: evaluation package exists, judge client proven on one hand-driven case.

- `tests/evaluation/` package (own `pyproject.toml` + `requirements.lock`
  via `uv pip compile`, pattern of `tests/contract`):
  - `config.yaml` — judge config per evaluation-tests.md: model
    `gemini-2.5-pro`, temperature 0, candidate_count 1, `judge.md_sha256`;
    the runner records returned publisher model/version metadata into the
    typed run result.
  - `prompts/judge.md` — judge prompt (repo `prompts/` root, alongside agent
    prompts; content-hash pinned by config). Prompt states: inputs are the
    case's captured typed outputs + the expected-file outcome; score five
    dimensions 0–4 (review coverage, grounding, conflict resolution,
delegation, final-state quality); issue list with severity incl.
    `blocker`; output = strict JSON matching `JudgeResult`
    (`docs/design/schemas.md`). No agent state shared.
  - `judge_client.py` — plain stateless Vertex call (reuse agent-kit's
    Vertex call pattern), temperature 0, one candidate; policy: one retry
    on transient transport failure with identical input; invalid structured
    output or second transport failure = case failed; **no best-of-N ever**.
  - `runner.py` (skeleton) — loads a case, drives orchestration, captures
    typed outputs, placeholder assertion hooks, saves artifacts.
  - `models.py` — `JudgeResult` (+ run-result types) per schemas.md; kept
    suite-local unless review-schemas bump is cheaper (settle: if any other
    unit must consume it, it moves to review-schemas; otherwise local).
- `Makefile`: `evaluation-test` + `evaluation-smoke` targets
  (pattern of `orchestration-integration-test`: requires
  `agents-compose-up`, throws throwaway migrated Postgres, provides env).
- Unit tests: judge_client retry/fail policy against a fake Vertex
  transport; JudgeResult validation (thresholds, dimension completeness);
  config sha check. One optional live smoke: judge call on a canned
  clean-case transcript (single Vertex call) — run only when the owner
  approves spend.

Gate: unit tests green; package lint/format per repo standards; make targets
exist and fail cleanly without a running stack.

### Increment 1 — Deterministic assertion engine (judge OFF)

Goal: data-driven runner executes all 45 cases against the local compose
stack and evaluates every deterministic assertion.

- `case_runner.py`: per (scenario, story) — create session (idempotency key
  discipline as the webui: key persisted before POST, 503 same-key retry),
  replay `po_script` steps (message turns; `po_accepted: true` = acceptance
  turn triggering synchronous finalize), collect TurnResponse +
  SessionDetail per turn. Subset control: `--templates t1` (10 cases) for
  cheap iteration; full set at milestones. Output: per-case JSON artifact
  (all typed outputs + durable ids) + summary.
- `assertions.py` — assertion functions, each independently unit-tested
  against recorded fixtures (fake TurnResponse/session JSON incl. deliberate
  failure fixtures; no model calls):
  - turn structure: outcome, state_after, produced artifact set + versions
    per `expected_turns` (exact);
  - delegation: invoke target, reuse_previous, extra-context presence —
    exact (discrete decision);
  - findings: required keys set-based (B-*/E-* semantic keys), min_severity,
    appears_in_version, resolved_at_turn; `max_severity` ceiling per review;
  - conflicts: keys/kind at_turn_1/later, resolved_at_turn — set-based;
  - final: state, final_turn_number, facilitator_turn_count, po_accepted,
    remaining_open_issues_empty, requested report formats present as
    artifacts + signed URLs returned;
  - fan-out/order: from `agent_runs` rows — reviewer spans of the same turn
    overlap, synthesis run starts after both reviewer runs of that turn,
    every run names its agent, caller = orchestration (local equivalent of
    the deployment-ID assertion: distinct adapter service identities);
  - MCP evidence (comment scenarios): ≥1 facilitator-initiated story-MCP
    tool call in the turn trace (paired tool events already emitted);
  - persistence (runner-level, on selected cases): after completion/abandon,
    restore session by id (list/detail ok), same-run artifact reads succeed,
    cross-run artifact reads rejected; unresolvable case asserts park at
    exactly turn 10 with the session_parked event;
  - invariance: free — all templates assert against the same expected file;
    a template-specific failure is reported tagged with the template.
- Triage protocol (in-plan, executed as the increment's main work):
  every failing assertion labeled CODE (orchestration bug → fix test-first
  per development-rules), DATASET (story/expected gap → increment 2), or
  PROMPT (behavioral miss → increment 3). Triage log kept in the runbook.
- Reuse: the Phase-6 `orchestration/tests/integration` harness pattern
  (live_env, compose stack, throwaway Postgres) — but evaluation runs over
  real HTTP against the compose services, like the webui does, so sessions
  are durable and restore/persistence assertions are honest.

Gate: `make evaluation-test TEMPLATES=t1` runs 10 cases deterministic-only
and produces per-case artifacts; assertion unit tests green; CODE-class
failures fixed test-first and re-run.

### Increment 2 — Dataset tuning pass (owner-reviewed)

Goal: every evaluation-tests.md "what is tested" row has ≥1 strong case,
and failing DATASET-class cases are repaired.

- Input: increment-1 triage log + a scenario-representativeness review
  (walk the 8 tested aspects × 10 scenarios; flag weak/absent coverage —
  e.g. re-review synthesis new-conflict detection is only implicit today;
  also sanity-check oddities noticed while planning: `conflicting` and
  `hidden-conflict` expect `state: completed` with `po_accepted: false` —
  confirm the facilitator-gate finalize path is intended and covered).
- Story edits happen in the ADO source of truth + re-export
  (`dataset/tools/export_ado.py`; `set -a; source infra/envs/ado.env; set +a`);
  export diff reviewed before commit. `dataset/expected/*.json` and
  `dataset/manual-plans/*.md` updated in step; `make dataset-test` green.
- If a tuning change alters what a scenario proves, the expected file's
  `semantic_notes` are updated to say so (they are the human audit trail).
- Re-run increment 1 (t1 subset → full if structural changes) until the
  DATASET bucket is empty or everything left is PROMPT-class.

Gate: dataset matrix consistent (loader tests), t1 subset deterministic run
shows no DATASET-class failures; owner reviews the ADO + expected diffs.

### Increment 3 — Judged full set + prompt tuning loop

Goal: judge wired in; every required case passes deterministic + judged;
smoke set defined.

- Wire judge into the runner: judge called only for cases passing
  deterministic assertions (cost control); one call, ≤1 identical retry;
  pass = every dimension ≥3, mean ≥3.5, no blocker issues; results typed,
  saved per case; aggregate trend report (JSON + markdown summary).
- Prompt tuning: PROMPT-class failures + judge sub-3 dimensions →
  hypothesis → minimal `prompts/*.md` change → re-run affected cases (t1
  subset) → re-run full set at milestones. Every prompt change is versioned
  by git (the designed evaluation trigger); changes recorded in the
  runbook with before/after case results.
- Smoke set (the pipeline-gate design, run locally): all deterministic
  structural assertions across the t1 subset + one end-to-end judged happy
  path (`clean`). `make evaluation-smoke`.
- Documented-instability policy: case failing only on demonstrated
  quota/5xx evidence in the trace → one rerun, both raw outputs kept.

Gate: full required set (45 cases) passes deterministic + judged locally;
smoke set green; artifacts retained.

### Increment 4 — Dev-mode run (deployed environment)

Goal: same suite passes against dev (public domain), proving the suite and
the system as deployed.

- Cloud SQL resumed (`make db-resume`) for the run; paused after (gotcha:
  first-attempt startup-probe race possible — retry).
- If prompts changed in increment 3: facilitator (and affected reviewers)
  redeployed with new versioned labels, per-engine smoke PASS, orchestration
  pointers updated — before the evaluation run.
- Dev-mode runner differences: base URL = public domain (through webui /api
  proxy or direct orchestration URL with ID token, whichever the suite can
  authenticate — settle at increment 4; x-user-id header required);
  deployment-ID assertion switches to the real Agent Engine resource
  identities from agent_runs audit fields; AE session-reconciliation
  surface available for facilitator-turn evidence if needed.
- Evidence: Runbook 15 — case results, correlation ids, model/judge config
  metadata; cost observations recorded.

Gate: full set green against dev; Cloud SQL paused; runbook updated.

### Increment 5 — Close

- `docs/quality/requirements-coverage.md`: "Agents evaluation tests
  implemented" → verified with evidence; rows citing "integration tests"
  that this suite now covers (session management/persistence, session
  context, MCP-on-Cloud Run integration) upgraded with pointers to
  Runbook 15 artifacts. (docs/ change → frozen cherry-pick if evaluation
  docs text changes; status flips in coverage are `docs/` edits too —
  cherry-pick accordingly.)
- Phase-close review (read-only subagent); findings fixed/recorded.
- development-plan Phase 9 → COMPLETE (demo deferred per D29-1 — it opens
  the next phase); HANDOFF update; commits per convention (owner pushes).

## Exit criteria (amended)

All required dataset cases pass (deterministic + judged) locally and against
dev; smoke set green; tuning changes committed; coverage table updated with
evidence; phase review Ready-to-close. Demo: **deferred to next phase** (D29-1).

## Risks / notes

- Judge stability: policy already fixed (one retry, no resampling); a case
  failing solely on demonstrated model-service instability gets one
  documented rerun with both raw outputs kept.
- Cost control: prefer deterministic-only runs while iterating; judge calls
  only on deterministic-passing cases.
- Local vs dev parity: assertions on "distinct Agent Engine deployment
  resource IDs" only apply in dev mode; local mode asserts distinct adapter
  service identities (equivalent structural claim).
- Any orchestration code fixes found by the suite follow the normal
  test-first development rules; dataset/prompt-only changes need no frozen
  cherry-pick (docs/ untouched unless schemas change).
