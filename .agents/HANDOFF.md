# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. Last updated: 2026-09-07 (session 12: Phase 2 post-review accepted +
commit `2d639b3`; Phase 3 plan written, ADO sample environment stood up
(Runbook 08), dataset template matrix designed; story authoring in progress).

## Where we are

- Phase: **3 — Mock dataset: IN PROGRESS** (plan at
  `docs-local/plans/phase-3-mock-dataset.md`; ADO env + backlog structure done
  in Runbook 08; dataset/expected work tracked in Runbook 09).
- Phase 2 COMPLETE and post-reviewed (session 11, owner-run: independent review
  + 41 negative tests added, suite **147 passed**; commit `2d639b3`).
- Phase 1 complete: end-to-end trace passed under the D8 ingress fallback; all
  spike resources torn down (Runbook 06).
- Docs design: complete and frozen on branch `docs/initial-frozen` (`d5cb413`);
  home-phase docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`); owner
  pushes (`main` + `docs/initial-frozen`).

## Previous Session Summary

Session 12 (2026-09-07) — Phase 2 accepted; Phase 3 opened; ADO sample env;
template matrix (local-only; Cloud SQL stayed STOPPED). Owner ran the Phase 2
post-review independently (independent review + missing negative tests,
147 passed, Runbook 07 marked COMPLETE). Phase 3 plan written
(`docs-local/plans/phase-3-mock-dataset.md`, increments 0-4) and Runbook 09
opened. Story format decided: mimic a real **Azure DevOps work-item export** —
free org (Basic plan, no cost, no subscription used; the account's free-trial
Azure subscription must stay unused), owner-created org `$ADO_ORG`, project
`story-review` created **Agile** (first attempt was accidentally Basic and was
deleted/recreated — base process is immutable). Runbook 08 codifies: mise
azure-cli 2.90.0 + azure-devops extension, `az login`, org/project setup,
iteration/area + work-item CLI gotchas. Backlog structure built via CLI:
Sprint 1-3 (dated), Epic "Payment Platform Expansion" (id 2), Features
"Alternative Payment Methods" (3) / "Checkout Reliability" (4). Stories live
in the BACKLOG (pre-estimation, no Effort field); tasks were created then
DELETED (owner-approved) — stories are self-contained. Dataset template matrix
designed in `dataset/story-templates.md`: template vs. story-quality as
independent axes; **format invariance** as the system requirement under test;
canonical content model (variants rendered from per-scenario canonical facts);
T1-T6 (structured / sectioned maintenance / job story / classic user story /
enabler-as-TYPE-variant / free text); HTML split out as a Phase 4 ingestion
stress. Independent subagent review of the template design: 4 Important
findings, all adopted. The six T1 baseline stories are COMPLETE: id 5 clean
(Invoice PDF in confirmation email), id 10 business-weak (Google Pay at
checkout), id 14 engineering-weak (Automatic payment retry on PSP failure),
id 17 conflicting (Auto-select last used payment method at checkout), id 18
partial-resolution (Save payment details for returning customers — mirror of
example-interaction.md `story-04`), id 19 unresolvable/park-at-cap (Localize
checkout for international customers). Owner then extended coverage with a
7th scenario (docs/quality/mock-data.md table row added, owner-approved):
HIDDEN-CONFLICT — id 20 "30-minute order edit window after purchase" under
Feature 4: both reviews individually positive (engineering hook: "captures
payment immediately at order placement"; business hook: "payment only
reserved… release is free"), synthesis must flag the contradiction with
zero per-perspective findings. All hierarchy-verified, tagged, backlog
iteration. T1 baseline column: 7/7.
- Session 13 (continued): seven per-scenario manual test plans in
  `dataset/manual-plans/` (PO scripts + expected turns, keyed by scenario —
  format invariance); D9 recorded (canonical case ids, not ADO ids;
  JSON/mock-endpoint story serving; one area path per template — T2–T6
  areas created); T2 column drafted by subagent from T1 canonical facts
  (`dataset/drafts/t2/`, reviewed PASS) and authored in ADO as ids 21–27
  (area `T2`, AC field empty — the T2 field-location test).
- Session 13 (continued): canonical fact document `dataset/canonical-facts.md`
  authored (per-scenario facts / criteria / must-not-add / title /
  provenance, linked from story-templates.md) — the retro-write canonical-
  facts task is DONE; it is the authoritative renderer input for T3–T6.

### Earlier sessions (digest — detail lives in runbooks and git history)

- Session 11 (2026-09-07, owner-run): Phase 2 post-review — no contract
  divergences; 41 negative tests added for api/records validator branches;
  suite 147 passed; commit `2d639b3`.

- Session 10 (2026-09-06): Phase 2 increments 4 + phase close (MCP models,
  install proof, export-list test; suite 142) and the second history-redaction
  pass (owner-run filter-repo; rewritten `main` `649f7c4` force-pushed; zero
  ID hits; teardown of clone dir + /tmp rules file pending with owner).
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

Session 12:
- Phase 2 post-review (owner-run, session 11): suite **147 passed**;
  `2d639b3` verified and accepted.
- ADO environment: every step executed via codified Runbook 08 commands and
  evidenced (CLI-verified org/project/types/iterations; hierarchy links
  verified via `--expand relations`; deletes verified children=0).
- Template design: independent read-only subagent review — 4 Important / 4
  Minor findings; all Important + 3 Minor adopted into
  `dataset/story-templates.md`; deferred items recorded in Runbook 08.
- No test-suite changes this session (dataset code comes in Runbook 09
  increments); `make review-schemas-test` not re-run (no schema code touched).

Sessions 3–11: verification evidence is recorded per action in Runbooks
03–07 (Terraform init/fmt/validate/plan, owner-reviewed applies, gcloud
cross-checks, test-first red/green, review findings fixed).

## Remaining Tasks

- **Phase 3 continuation (Runbook 08/09, next session):** retro-write canonical
  fact lists for all seven T1 stories (5/10/14/17/18/19/20 — the T1 column is
  complete; id 20's must-not-add list must forbid clarifying the capture
  model); then export script + remaining D9 items (fidelity/trimming,
  metadata classification — ID-decoupling, JSON/mock-endpoint serving, and
  the ADO matrix structure [one area path per template, T2–T6 areas created]
  are already recorded/settled in local-decisions.md D9); then Runbook 09
  dataset/expected/loader work.
- ~~Owner teardown of the redaction pass~~ DONE (2026-09-07, owner):
  `~/projects/capstone-project-filter2` removed; `/tmp/project-id-replace.txt`
  left in place deliberately (tmp clears itself).
- Azure DevOps note: the ADO org's free-trial Azure subscription must stay
  unused; only `az devops`/`az boards` commands touch the org.
- Optional: fix the broken glab git-credential helper path (mise install;
  cosmetic warning during fetch).
- Optional later increment: tighten the default compute SA's `roles/editor`
  (pre-existing from project creation).
- Phase 0 exit criterion "terraform apply reproducible from clean (destroy +
  apply)" was not re-proven by a destroy cycle (destructive, deferred unless
  needed); config is tfvars-driven.

## Next Steps

1. Owner pushes `main` (session-12 commit).
2. Next session: T3–T6 columns (same draft → review → author flow; T5 is
   the enabler TYPE variant — self-contained, not renderings), then
   export + remaining D9 items; Runbook 09 increments 1–4 (expected files
   transcribed from the plans, loader harness, `make dataset-test`).
4. Keep Cloud SQL paused until a phase needs it.

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only;
  pipelines written at promotion (local-decisions.md D3).
- Git: session 11's `2d639b3` and the session-12 commit are local until the
  owner pushes; before that, remote sits at the rewritten `main` `649f7c4`
  (76 commits, zero ID hits, `docs/initial-frozen` = `d5cb413` unchanged).
  Old hashes (`a519899`, `bcd1c1b`, `dadd2e1`, `9482e6a`) are superseded.
  Check `git status -sb` before assuming the remote is current — tracking
  refs can be stale.
- Azure DevOps (Phase 3 ground truth): free org `$ADO_ORG` (gitignored
  `infra/envs/ado.env`, sourced alongside `home.env`); project `story-review`
  (Agile process); work item IDs are org-wide and never reused (project starts
  at id 2 after the deleted Basic project consumed id 1). az CLI via mise
  (`azure-cli` 2.90.0 + `azure-devops` extension). Story content conventions:
  backlog iteration, no Effort, self-contained stories (no tasks);
  `dataset/story-templates.md` is the authoritative template/matrix doc.
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
