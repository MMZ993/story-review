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
