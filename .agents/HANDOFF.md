# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-06 (session 10: Phase 2 increment 4 + phase close and
second history-redaction pass — MCP models, install proof, export-list test, diff
review, independent review, owner-run filter-repo; Phase 2 COMPLETE, history clean,
remote in sync).

## Where we are

- Phase: **2 — Shared schemas: COMPLETE** (all four increments done; plan at
  `docs-local/plans/phase-2-shared-schemas.md`, evidence and phase-close PASS
  in Runbook 07).
- Phase 1 complete: end-to-end trace passed under the D8 ingress fallback; all
  spike resources torn down (Runbook 06).
- Docs design: complete and frozen on branch `docs/initial-frozen` (`d5cb413`);
  home-phase docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`); owner
  pushes (`main` + `docs/initial-frozen`).

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
aliases present. Independent read-only review (subagent): 2 findings —
missing valid-boundary cases (limit 1/500, items 500) and missing `mcp.py`
class docstrings — both fixed, suite re-run green. Phase 2 exit criteria
PASS; evidence in Runbook 07 §Increment 4. Lock recompile at close: content
identical (header comments are invocation-dependent cosmetics).

Session 10 addendum (same day) — second history-redaction pass EXECUTED
(owner-run `git filter-repo --replace-text` in a fresh local clone; what was
done and the gotchas are recorded here — the procedure itself is standard and
deliberately not kept as a runbook; it is repo hygiene, not project work).
Scope: the project ID that had leaked back into this file via session 8's
wrap-up commit (`a519899`), removed from the tree in `9482e6a`. Only those
two commits contained it; pre-`a519899` hashes and all of `docs/initial-frozen`
(`d5cb413`) unchanged. Rewritten `main` tip `649f7c4` force-pushed (the
remote had been at `bcd1c1b` — session 8/9 chore commits were never pushed);
working copy resynced and in sync, 76 commits, zero ID hits anywhere.
Key gotchas learned: filter-repo removes the origin remote by design
(re-add + fetch before pushing); `git log --all` in a fresh clone includes
the old fetched remote-tracking refs (scope checks to the branch until
teardown); always `git fetch` before choosing a `--force-with-lease` target;
run the final `-S` check *after* the session's last commit that discusses
the identifier. Teardown (clone dir + /tmp rules file) pending with the owner.

### Earlier sessions (digest — detail lives in runbooks and git history)

- Session 9 (2026-09-06): Phase 2 increments 1–3 — package skeleton and
  strict primitives, error + domain groups, API + durable records; 99 tests.
  Evidence and gotchas in Runbook 07.
- Session 8 (2026-09-06): docs hardening — CR→AE test gap recorded as a
  Phase 8 exit criterion; docs-first rule added to AGENTS.md; repo scanned
  for company-internal material (none found); first history rewrite
  (Runbook 06 project-ID redaction).
- Session 7 (2026-09-06): reviewed Phase 1 evidence; wrote the Phase 2
  master plan (`docs-local/plans/phase-2-shared-schemas.md`).
- Session 6 (2026-09-05, evening): Runbook 06 increment 4 — Agent Engine
  caller proven with the persist/restore trace; D8 ingress fallback applied.
- Session 5 (2026-09-05): Runbook 06 increments 1–3 — interfaces confirmed,
  spike store/MCP/agent implemented, Cloud SQL IAM-db-auth + schema, Cloud
  Run MCP service deployed. D7 recorded.
- Session 4 (2026-09-05): verified Phase 0 inventory vs Terraform (no
  drift); wrote the Phase 1 plan.
- Session 3 (2026-09-05): Phase 0 bootstrap in three evidenced Terraform
  increments — service accounts (Runbook 03), resource skeletons (Runbook
  04), exit checks + smoke test (Runbook 05). D6 recorded.

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
- Post-redaction: 76 commits, `docs/initial-frozen` unchanged, `git fsck`
  clean, zero ID hits in working copy and rewritten history, remote in sync
  at `649f7c4`.

Sessions 3–9: verification evidence is recorded per action in Runbooks
03–07 (Terraform init/fmt/validate/plan, owner-reviewed applies, gcloud
cross-checks, test-first red/green, review findings fixed). Session 9's
suite count: 99 passed at phase increment 3.

## Remaining Tasks

- Owner teardown of the redaction pass: `rm -rf
  ~/projects/capstone-project-filter2` and `rm /tmp/project-id-replace.txt`
  (the latter contains the literal ID).
- Optional: fix the broken glab git-credential helper path (mise install;
  cosmetic warning during fetch).
- Optional later increment: tighten the default compute SA's `roles/editor`
  (pre-existing from project creation).
- Phase 0 exit criterion "terraform apply reproducible from clean (destroy +
  apply)" was not re-proven by a destroy cycle (destructive, deferred unless
  needed); config is tfvars-driven.

## Next Steps

1. Commit the session-10 addendum (HANDOFF only) — `chore:` commit,
   then owner pushes.
2. Session 11: Phase 3 planning per `docs-local/development-plan.md`
   (dataset files and expected outcomes); Phase 2 closed with no GCP or
   database dependency.
3. Keep Cloud SQL paused until a phase needs it.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only;
  pipelines written at promotion (local-decisions.md D3).
- Git: as of session 10's second redaction pass, everything is pushed and
  verified — working copy and internal GitLab both at rewritten `main`
  `649f7c4` (76 commits, zero ID hits, `docs/initial-frozen` = `d5cb413`
  unchanged). Old hashes (`a519899`, `bcd1c1b`, `dadd2e1`, `9482e6a`) are
  superseded. Check `git status -sb` before assuming the remote is current —
  tracking refs can be stale.
- **History rewrites end at publication.** Once the repo goes public, no
  filter-repo passes are possible — so the identifier check
  (`git log --all -S "$PROJECT_ID"`, after sourcing `infra/envs/home.env`)
  plus a secrets/identifiers review is a mandatory pre-mirror gate, and it
  must run *after* the last commit of the session performing it.
- Evidence sanitization: no persistent identifiers in pasted evidence — use
  the `$PROJECT_ID` / `<real-project-id>` forms (rule in AGENTS.md since
  session 8).
- Spike resources REMOVED (Runbook 06 increment 5): Cloud Run service, agent
  engine, AR images, `spike` schema gone; terraform clean. Spike source,
  tests, and runbook evidence preserved in git.
- Cloud SQL instance is **PAUSED** (state STOPPED/NEVER) — run
  `make db-resume` before any phase that needs the DB (`db-pause` /
  `db-resume` / `db-status` Make targets are PROJECT_ID-guarded).
- Trial credits: near-zero used of zł1,114, expire 2026-12-05. Old default
  trial project exists but is unused/ignored.
- Repo content: scanned for company-internal material — none found (only
  sanitized capstone requirements in `docs/source/`; owner decides whether
  they stay in a public mirror). GitHub mirror pending (owner, via GitLab
  GUI); keep the repo private until final review.
