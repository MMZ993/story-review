# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D15),
`docs-local/development-plan.md` (phase scope/exit criteria), and git history
(the record of what changed). Do not let this file grow back into an archive.

Last updated: 2026-09-13 (session 34 — Item D callback-completion entry in
future-extensions; marker added to HANDOFF).

## Where we are

- **Phase 6 — Orchestration (FastAPI): OPEN, increment 0 GREEN** (session 33;
  detail in Runbook 12). Plan `docs-local/plans/phase-6-orchestration.md`
  (increments 0–5), decisions **D15** settled. **Next: increment 1** (MCP
  client wrapper + stories endpoints + real /health).
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

- review-schemas **154**, ado-wire **7**, dataset **36**, mcp-ingress **7**,
  mcp-story **67**, mcp-artifact **32**, mcp-report **34**, compose contract
  **20**, agent-kit **82**, agents skeleton **4×4**, business adapter
  **6+2s**, engineering adapter **7+1s**, synthesis adapter **7+2s**,
  facilitator adapter **3+1s**, orchestration **19** (increment 0); live gates: business/engineering/synthesis
  adapters + facilitator walkthrough all PASS (Runbook 11).
- Per-session verification evidence (commands, counts, review verdicts,
  gotchas): append-only in the runbooks — Runbook 11 §0–4 + completion
  review for Phase 5; Runbook 10 for Phase 4; earlier phases in 03–09.
- Review discipline: independent read-only subagent review per significant
  increment and at phase close; verdicts recorded in the runbook sections.

## Remaining Tasks

- Phase 6 increments 0–5 per the plan (Runbook 12 tracks progress).
- Deferred review minors (fix in Phase 6 where natural, else later):
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

1. Commit session 33 (orchestration increment 0 + Runbook 12 + HANDOFF) —
   explicit paths, on owner approval; owner push (main ahead 3 + this commit).
2. **Phase 6 increment 1** (next session): MCP client wrapper
   (timeouts/retries/deadline clamping), `GET /api/v1/stories[/{id}]`, real
   `/health` with downstream flags; deterministic tests against the compose
   `local` stack.

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
- **Local stack**: `make agents-compose-up` (local + local-agents profiles;
  needs host ADC); `compose-contract-test` needs `compose-up` first.
- **Keep private** until final review; GitHub mirror pending (owner).
- Repo layout/plans/runbooks index: `docs-local/development-plan.md` and
  the per-phase plans under `docs-local/plans/`.
