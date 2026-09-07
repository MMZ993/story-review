# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
Last updated: 2026-09-08 (session 14: T5 + T6 authored — matrix COMPLETE;
  export done (Runbook 09 increment 1, 45 sanitized JSON files); next:
  expected files + loader).

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
  T3 (job story, ids 28–34) and T4 (classic user story, ids 35–41) drafted
  from it by parallel subagents, independently reviewed (14/14 PASS), and
  authored in ADO (areas T3/T4, AC field = informal bullets, T4 titles =
  full story sentences). Matrix columns T1–T4 complete (7 scenarios each).
- Session 14 (continued): T5 column authored. Design decision (owner-approved):
  each T5 enabler is the engineering-side counterpart of its scenario — same
  story world, planted flaw preserved verbatim, expected review arc identical
  to the scenario's manual plan (T5 stays excluded from cross-template
  invariance assertions per story-templates.md; verdict-mirroring is by
  design). Authoring input `dataset/t5-enabler-spec.md` (framing, facts,
  criteria, must-not-add, expected verdict per scenario; extra business-weak
  clause: no technical-effort justification standing in for business value).
  Drafts in `dataset/drafts/t5/` (subagent, t3-style with self-check);
  independent read-only subagent review: all substantive checks PASS (only
  the authoring-artifact self-check sections were flagged — not ADO content).
  ADO ids: clean 42, business-weak 43, engineering-weak 44, conflicting 45,
  partial-resolution 46, unresolvable 47, hidden-conflict 48 — area `T5`,
  backlog iteration, tags identical to T1 mirrors, parents verified
  (42→4, 43→3, 44→4, 45→3, 46→3, 47→3, 48→4), AC bullets verified, id 48
  carries both capture statements unreconciled. Matrix T1–T5 complete; T6
  (free text, must carry every canonical fact) remains.
- Session 14 (continued): T6 column authored — the MATRIX IS COMPLETE
  (T1–T6 × 7 scenarios, ADO ids 5–55). Drafts in `dataset/drafts/t6/`
  (subagent from `dataset/canonical-facts.md`, quick-notes register, terse
  titles, criteria woven into plain prose); independent read-only subagent
  review: **7/7 PASS** (every fact/criterion/scope present, all planted
  gaps absent, hidden-conflict both capture statements unreconciled, no
  lists/scaffolding). ADO ids: clean 49, business-weak 50, engineering-weak
  51, conflicting 52, partial-resolution 53, unresolvable 54,
  hidden-conflict 55 — area `T6`, backlog iteration, terse titles
  ("Invoice mail", "GP", "retry", "last one", "saved card", "intl",
  "30m edit"), AC field EMPTY (the T6 no-criteria-field stress), tags
  identical to T1 mirrors, parents verified (49→4, 50→3, 51→4, 52→3,
  53→3, 54→3, 55→4). canonical-facts.md provenance lines now carry all
  template ids (T1–T4 retro-added, T6 added).
- Session 14 (continued): **export done (Runbook 09 increment 1)**.
  `dataset/tools/export_ado.py` exports the full matrix to
  `dataset/stories/`: per-template folders `t1`–`t6` + `context/` (epic+
  features), case id = `<template>/<scenario>` (**owner rule: 1 test case =
  1 story in 1 template**; stress duplicates get `-2` suffixes = separate
  test cases), ADO id demoted to `ado_source_id`. Envelope + verbatim
  `work_item` (owner decision: export VERBATIM, preparation/trimming is a
  separate later step). Sanitization: `_links` dropped, URLs rewritten to
  `$ADO_ORG`/`<project-id>` (org name + project GUID leak via imageUrl/
  relation/url fields — caught post-export); author identities anonymized
  to `Story Author`/`<author>@example.com` with account ids dropped
  (owner decision: personal data stays out of git). Story→case resolution:
  area path → template, provenance ids (canonical-facts + t5-enabler-spec)
  → scenario; loud aborts + count asserts (42+3). Post-export checks all
  pass (45 files, zero identifier hits). `dataset/README.md` written;
  D9 amendment recorded in local-decisions.md; Runbook 09 increment 1
  marked DONE (increments 0–2 done; next: 3 = expected files, 4 = loader).

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

Session 14:
- T5 and T6 drafts: independent read-only subagent reviews — T6 7/7 PASS;
  T5 all substantive checks PASS (sole flag: the self-check authoring
  artifacts — reviewer miss, not a defect).
- ADO authoring verified per item live: area path, backlog iteration,
  tags, parent links (Hierarchy-Reverse), AC bullet counts; id 48/55 both
  capture statements unreconciled; WIQL confirms exactly 42 stories +
  epic/features (ids 5–55).
- Export: post-export checks all pass — 45 files, envelope shape, zero
  identifier hits (org name, project GUID, owner email, MSA descriptor,
  visualstudio tenant URL, `_links`); identifier check run BEFORE commit
  (AGENTS.md rule).
- No schema/test code touched: `make review-schemas-test` not re-run
  (loader/dataset tests are Runbook 09 increment 4).

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

- **Phase 3 continuation (Runbook 09, next session):** increments 0–2 DONE
  (matrix authored + exported); next is increment 3 — expected files
  transcribed from `dataset/manual-plans/` into
  `dataset/expected/<template>/<scenario>.json` (7 scenarios × 6 templates,
  vocabulary per docs/design/schemas.md, deterministic assertions per
  docs/quality/evaluation-tests.md) — then increment 4 (loader harness,
  test-first, `make dataset-test`). Deferred D9 items still open:
  fidelity/trimming (separate preparation step against the verbatim
  export) and metadata semantic/display classification (expected-file
  design time).
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

1. Next: Runbook 09 increment 3 (expected files transcribed from
   `dataset/manual-plans/` into `dataset/expected/<template>/<scenario>.json`)
   and increment 4 (loader harness, test-first, `make dataset-test`).
   Export/increment 1 done this session; matrix COMPLETE (ids 5–55).

## Important Notes

- Deployment pipeline stance: none yet — local scripts + runbook only;
  pipelines written at promotion (local-decisions.md D3).
- Git: session 14 produced six commits (`a74bcc6`, `1f39e19`, `310765a`,
  `73bd8a5`, `5b00339`, `07b6d5f`); the first four are pushed by the owner,
  the last two (`5b00339` export+JSON, `07b6d5f` docs) are local until the
  owner pushes — remote `main` currently at `73bd8a5`. Old history note:
  `docs/initial-frozen` = `d5cb413`; superseded hashes `a519899`,
  `bcd1c1b`, `dadd2e1`, `9482e6a`, `649f7c4` were from the rewrite era.
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
