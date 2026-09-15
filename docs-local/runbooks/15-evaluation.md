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
