# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-06 (session 10: Phase 2 increment 4 + phase close —
MCP models, install proof, export-list test, diff review, independent review;
Phase 2 COMPLETE).

## Where we are

- Phase: **2 — Shared schemas: COMPLETE** (all four increments done; plan at
  `docs-local/plans/phase-2-shared-schemas.md`, evidence and phase-close PASS
  in Runbook 07).
  Phase 1 is complete: its end-to-end trace passed with D8 fallback and all spike
  resources were torn down (Runbook 06 increment 5).
- Docs design: complete and frozen on branch `docs/initial-frozen`; home-phase
  docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`);
  owner pushes (`main` + `docs/initial-frozen`).

## Previous Session Summary

Session 10 (2026-09-06) — Phase 2 increment 4 + phase close (local-only; Cloud
SQL stayed STOPPED). Implemented `review_schemas/mcp.py` verbatim from the
spec's MCP section (inline dicts extracted as named helpers, observable
behavior unchanged) with the eleven MCP models; extended public `__init__`
exports to 75 names. Tests written first and confirmed red on
ModuleNotFoundError. `test_mcp_models.py` (39 tests): save/get exact-type
checks, perspective rules incl. review-content mismatch and final-review
cross-run, get output reference↔content match (report-* rejected), list
filter compatibility and bounds/boundary values, render input run+type and
output format↔reference. `test_package_install.py` (4 tests): mechanical
export-list equality against a spec-derived 75-name list, `ArtifactRecord`
internal, and a genuine clean-venv path-install proof (uv venv + locked
requirements + `--no-deps` path install; python run from `/tmp` asserts
version 0.1.0, full `__all__`, site-packages provenance). Mechanical
named-model diff vs `docs/design/schemas.md`: all 56 classes and all type
aliases present. Independent read-only review (subagent) returned two
findings — missing valid-boundary cases (limit 1/500, items 500) and missing
`mcp.py` class docstrings — both fixed, suite re-run green. Phase 2 exit
criteria PASS; evidence in Runbook 07 §Increment 4. Lock recompile at close:
content unchanged, test-lock header comment corrected (increment-2 cwd
leftover). **Uncommitted at this writing** (owner decides commit).

Session 9 (2026-09-06) — Phase 2 increments 1–3 (local-only; Cloud SQL stayed
STOPPED). Increment 1: created `shared/review_schemas` (pyproject v0.1.0, hatchling,
pydantic 2.13.5 lock; pytest-only test lock) with `review_schemas/base.py`
implementing the strict base types verbatim from `docs/design/schemas.md`, and the
Make target `review-schemas-test` (`--with-requirements` + `--with-editable .`);
26 tests test-first. Increment 2: implemented `errors.py`, `review.py`,
`synthesis.py`, `facilitator.py`, `judge.py` verbatim + public `__init__` re-exports
(`ArtifactRecord` deliberately internal); 36 new tests. Increment 3: implemented
`api.py` + `records.py` (HTTP request/response + canonical operation-result union,
and the five durable Cloud SQL record models) + extended exports to 64 names; 37
new tests (`test_api_models.py`, `test_records.py`; shared `artifact_reference`
helper moved to conftest). Suite now **99 passed**. Increments 1–2 committed
(`a4086b5`, `47c2d6c`); increment 3 uncommitted at this writing. Runbook 07 holds
evidence and gotchas (uv path/cwd resolution, editable-lock entries ignored,
hatchling README requirement, hyphenated-UUID IDs, Pydantic field constraints fire
before validators, alternate run-ID fixture pattern, required
Literal-without-default fields in CreateSessionResponse fixtures). Independent
review deferred to phase close (increment 4).

Session 8 addendum (2026-09-06) — see Session 8 summary above (CR→AE gap recorded).

Session 8 (2026-09-06) — docs hardening + pre-publication hygiene (no code, no
GCP changes; Cloud SQL remained PAUSED):

- Recorded the **Cloud Run (orchestration) → Agent Engine** test gap from Phase 1:
`development-plan.md` got a Phase 1 "deferred item" note and a Phase 8 exit
criterion (live proof: `sa-orchestration` IAM incl. `roles/aiplatform.user`,
`:streamQuery?alt=sse` from Cloud Run — Runbook 06 gotchas 3–4). Decision:
Phase 1 stays closed.
- Added a **docs-first rule** to `AGENTS.md`: consult `docs/`+`docs-local/`
before any task; on inconsistency, raise with the owner — never silently work
around or fix; record in local-decisions / change `docs/` with approval.
- **Repo scan for company-internal material** (files + full history, commit
metadata, remotes): none found. Only company-derived content is the sanitized
capstone assignment in `docs/source/` (no identifiers) — owner's call whether
it stays in a public mirror.
- **Project-ID redaction**: real GCP project ID appeared once in Runbook 06
(introduced in commit `d0e9a43`); removed from the tree; an **evidence
sanitization rule** added to `AGENTS.md` (no persistent identifiers in pasted
evidence — use `$PROJECT_ID` form; disposable random IDs acceptable).
- **Git history rewritten** (owner-run `git filter-repo --replace-text` in a
fresh clone, rule `<real-project-id>==>$PROJECT_ID`): 70 commits, zero
hits post-rewrite (verified); rewritten `main` force-pushed to the internal
GitLab; `docs/initial-frozen` untouched. Working copy resynced (HEAD =
origin/main = `e126e5b`, no diff, tree clean).
- Commits (post-rewrite hashes): `ee3c694` (deferred test item), `c907fc9`
(docs-first rule), `e126e5b` (project-ID redaction + sanitization rule).
- GitHub mirror deferred by the owner (to be added later via GitLab GUI); keep
the repo private until final review (incl. the `docs/source/` decision).

Session 7 (2026-09-06) — reviewed the completed Phase 1 evidence and wrote the
Phase 2 master implementation plan at `docs-local/plans/phase-2-shared-schemas.md`.
The plan defines the versioned `shared/review_schemas` package layout, dependency
locks, test-first implementation increments, independent-review gate, and zero-cloud
scope. `development-plan.md` now marks Phase 1 done; Cloud SQL status confirmed
`STOPPED/NEVER`. Plan reviewed with the owner: the domain group is split across
`review/synthesis/facilitator/judge` modules (module-size rule), and the development
rules gained a code-reads-like-a-book helper-extraction rule. No application code
changed and no environment action occurred.

Session 6 (2026-09-05, evening) — Runbook 06 increment 4 EXECUTED, PASS:
Agent Engine caller (`spike_agent/{agent,tools,transport}` +
`deploy-agent.sh`/`run-agent-trace.sh`) deployed and proven with the two-request
persist/restore trace (engine `3787430529595342848`, correlation
`1fe5d7f691e84ff689a2c9ba73b49dbf`; PASS asserted by jq guards). **Ingress
gate: internal ingress FAILED from Agent Engine (edge 404, no request logs);
approved fallback applied** — ingress `INGRESS_TRAFFIC_ALL` + mandatory
ID-token audience auth + invoker-only IAM, recorded as **D8** in
local-decisions.md. Extra applies during debugging: sa-facilitator →
roles/aiplatform.user (sessions permission), two MCP image rollouts (final
`spike-connectivity-mcp:20260905-2204-d0e9a43`, adds `requests`). Eight
gotchas recorded in Runbook 06 §Increment 4 (adk agent_engine_id update-only
400 + exit-0-on-failure; aiplatform.sessions.create needed; `:streamQuery`
not `:query` + snake_case events + JSON-not-SSE body; mcp 2.1.1 headers
kwarg removal; missing `requests` package; structuredContent fallback;
log-line wrapping vs correlation-ID search). Superseded agent engines deleted
by owner; spike code/tests/docs updated but NOT yet committed.

Session 5 (2026-09-05) — Runbook 06 increment 1: confirmed
interfaces (google-adk 2.8.0, mcp 2.1.1, google-cloud-aiplatform 2.1.0;
Agent Engine runtime SA via `.agent_engine_config.json` → `service_account=`);
14 deterministic tests for store/MCP-contract/agent-probe, implemented
`spikes/connectivity/{spike_mcp,spike_agent}` with locks and
`make spike-connectivity-test`; independent review findings fixed.
Increment 2: enabled `cloudsql.iam_authentication` + 4 IAM db users (Terraform;
two gotchas: flag name dot, SA username without `.gserviceaccount.com`);
applied spike schema/table/grants via one-time postgres admin session through
the Cloud SQL Python Connector on port 3307 (5432 blocked here; postgres
cannot SET ROLE to IAM roles). D7: admin password lives in gitignored
`home.env`, rotation procedure in Runbook 06 §2.5; Alembic rejected (D2 note).
Increment 2 committed as `9d92148`.
Increment 3 (same session, later block): Cloud Run MCP service —
`spike_mcp/{store_sql,auth_middleware,app,main}.py` (asyncpg over the
`/cloudsql` unix socket with IAM-db-auth token; pure-ASGI ID-token
middleware, fail-closed 503 on unset audience; stateless streamable-HTTP
app + `/healthz`), Dockerfile + `deploy-mcp.sh`, 12 new tests (26 total),
Terraform module `infra/modules/connectivity-spike` (count-gated on
`spike_mcp_image`) + root wiring. Independent review finding (check order)
fixed. Deployed via owner-run two-step apply (image
`spike-connectivity-mcp:20260905-1616-1bba7f7`, revision ...-00002) and
verified read-only via the Cloud Run v2 API. Commit pending at wrap-up.

Session 4 (2026-09-05) — verified the live Phase 0 inventory against Terraform:
project ACTIVE, billing enabled, all required APIs enabled, expected resource
counts present, and `terraform plan -detailed-exitcode` reported no drift. The
sanitized evidence is in Runbook 05. Wrote the Phase 1 implementation plan:
`docs-local/plans/phase-1-connectivity-spike.md`. It scopes the disposable
Agent Engine → authenticated Cloud Run MCP → Cloud SQL persist/restore proof,
initial internal-ingress test, permitted ID-token-authenticated fallback, exact
evidence, cost guardrails, and owner-run teardown.

Session 3 (2026-09-05) — finished the whole Phase 0 bootstrap in three
reviewed, evidenced Terraform/check increments, each committed atomically:

- **Runbook 03** (`docs-local/runbooks/03-service-accounts.md`):
  `infra/modules/service-accounts` — nine identity-model SAs (deployer + 8
  runtime) with pre-data-plane grants (deployer: run.admin / aiplatform.user /
  artifactregistry.writer / cloudsql.editor + actAs on each runtime SA;
  orchestration: aiplatform.user + tokenCreator on itself). Apply: 23 added.
  Commit `3c580d8`.
- **Runbook 04** (`docs-local/runbooks/04-resource-skeletons.md`): four new
  modules — Artifact Registry `service-images`; GCS bucket `<project>-artifacts`
  (report-prefix IAM condition, 90d report lifecycle); Cloud SQL POSTGRES_16
  `db-f1-micro`, ENTERPRISE edition, public IP + IAM-db-auth (fallback; final
  connectivity deferred to the Phase 1 spike — owner agreed); 8 empty
  per-service `<project>-<service>-config` secrets with least-privilege
  secretAccessor (own secret per runtime SA; deployer on all). Net: 34 added
  across three applies (two partial failures, gotchas recorded). Commit
  `f09bbf8`.
- **Runbook 05** (`docs-local/runbooks/05-phase0-exit-checks.md`):
  `scripts/smoke_vertex.py` (ADK LlmAgent + InMemoryRunner → Vertex via ADC) +
  Makefile skeleton (`smoke-vertex`, `terraform-plan/apply`, compose stubs).
  `make smoke-vertex` PASS (`gemini-2.5-flash`, europe-west4). Commit `1be8442`.
- **D6** (local-decisions.md): evaluation judge is not a deployed agent — ADC
  locally, deployer SA's aiplatform.user in CI; `sa-evaluator` is fallback only.
- Earlier sessions (context): runbooks 00–02 (tooling, gcloud setup/auth/ADC/
  billing/budget, Terraform API-enablement root + ten APIs).

## Verification and Review

Session 10:
- `make review-schemas-test`: **142 passed** (99 + 43 new), zero
  warnings/skips, after review fixes; `git diff --check` clean; both locks
  recompiled (content identical).
- Manual install probe from `/tmp`: version 0.1.0, import resolves inside
  venv site-packages (~0.5 s warm-cache).
- Named-model diff: 56/56 spec classes, all aliases present; `__all__`
  equals the spec-derived list; `ArtifactRecord` absent.
- Independent read-only review: 2 findings (Minor/Important), both fixed and
  re-verified; no unresolved findings.

Session 9:
- `make review-schemas-test`: 99 passed (increments 1–3), zero warnings/skips;
  `git diff --check` clean; test-first red confirmed for every increment.

Session 8:
- `git log --all -S <real-project-id>`: zero hits after the rewrite, in
  both the clean clone and the resynced working copy (HEAD = origin/main =
  `e126e5b`, `git diff origin/main` empty).
- Rewritten runbook line verified across all historical versions (`git grep`
  over `rev-list --all`): all show the `$PROJECT_ID` placeholder.
- Commit count preserved (70); `docs/initial-frozen` hashes unchanged.

Session 7 and earlier:

- All three runbooks: `init`/`fmt -check -recursive`/`validate` passed; plans
  reviewed by the owner before each apply; applies matched expected counts.
- Runbook 03: gcloud SA list, project IAM policy, and terraform outputs matched
  the plan exactly; no drift.
- Runbook 04: gcloud cross-checks (SQL instance, AR repo, bucket, 8 secrets)
  matched terraform outputs. Gotchas recorded in `.agents/infra-rules.md`:
  Cloud SQL ENTERPRISE edition required for `db-f1-micro`; Cloud SQL requires
  at least one connectivity path.
- Runbook 05: billing re-confirmed (`billingEnabled=True`); smoke test failed
  once on an ADK API detail (`create_session` requires `user_id`), fixed,
  then PASS. D1 checks 1–2 evidenced; Agent Engine bullets deferred to the
  Phase 1 spike by design (recorded in the runbook and development-plan).

## Remaining Tasks

- Session 10 output uncommitted: `shared/review_schemas` increment 4
  (`mcp.py`, `__init__.py` exports, both new test files, test-lock header
  fix) plus Runbook 07 increment-4 section and this HANDOFF update.
- Optional later increment: tighten the default compute SA's `roles/editor`
  (pre-existing from project creation).
- Phase 0 exit criterion "terraform apply reproducible from clean (destroy +
  apply)" was not re-proven by a destroy cycle (destructive, deferred unless
  needed); config is tfvars-driven.

## Next Steps

1. Owner: commit session 10 (agent proposes on request) and push session 9+10
  commits.
2. Session 11: Phase 3 planning per `docs-local/development-plan.md`
  (dataset files and expected outcomes); Phase 2 closed with no GCP or
   database dependency.
3. Keep Cloud SQL paused until a phase needs it.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only; pipelines
  written at promotion (local-decisions.md D3).
- Git: push state is the owner's; as of session 8 everything is pushed —
  working copy, clean clone, and internal GitLab all at `e126e5b` (rewritten
  history; old hashes like `c728b37`/`44b03ef`/`9d92148`/`f41ac10` are
  superseded). Check `git status -sb` before assuming the remote is current.
- Spike resources REMOVED (increment 5, 2026-09-06): Cloud Run service, agent
  engine, AR images, and `spike` schema gone; terraform plan clean (no drift).
  Spike source, tests, and runbook evidence preserved in git.
- Cloud SQL instance is **PAUSED** (`make db-pause`, 2026-09-06, state
  STOPPED/NEVER) — run `make db-resume` before any phase that needs the DB.
  New Make targets `db-pause`/`db-resume`/`db-status` (PROJECT_ID-guarded).
- Trial credits: near-zero used of zł1,114, expire 2026-12-05.
- Old default trial project exists but is unused/ignored.
- 2026-09-06 (pre-publication hygiene, session 8): real project ID redacted from
  Runbook 06 in tree AND git history (owner-run `git filter-repo`; verified zero
  hits; force-pushed). AGENTS.md gained an evidence-sanitization rule + docs-first
  rule. Repo scanned for company-internal material — none found (only sanitized
  capstone requirements in `docs/source/`; owner decides on including them in a
  public mirror). GitHub mirror pending (owner, via GitLab GUI); keep repo private
  until final review.
- 2026-09-06 (session 10): the real project ID had leaked back into
  `.agents/HANDOFF.md` (session 8's filter-repo rule note, added after that
  session's zero-hits check). Replaced with `<real-project-id>` in the tree;
  the literal value remains in **git history** — owner will run another
  `git filter-repo --replace-text` pass before any public mirror (decision:
  placeholder now + rewrite later).
- The rewrite's clean clone (`~/projects/capstone-project-clean`) was deleted by
  the owner after verification — it is no longer needed; the internal GitLab
  remote holds the rewritten history and is the source for the future GitHub
  mirror.
