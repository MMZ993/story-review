# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
Last updated: 2026-09-09 (session 18 — Phase 4 increment 1 correction:
  public story contracts no longer leak dataset evaluation metadata; shared
  schema 0.3.0, reviewed, suite 152 green).

## Where we are

- Phase: **4 — MCP servers + compose: IN PROGRESS** (session 17 opened it:
  plan + increment 0 done; next = increment 1, story MCP server).
- Phase 3 COMPLETE (session 16 close). Dataset: 45 stories (42 core + 3
  t1-only comment scenarios), 10 expected files; extension 2 (linked
  context stories) mock data deferred.
- Phase 2 COMPLETE and post-reviewed (session 11, owner-run: independent review
  + 41 negative tests added, suite **147 passed**; commit `2d639b3`).
- Phase 1 complete: end-to-end trace passed under the D8 ingress fallback; all
  spike resources torn down (Runbook 06).
- Docs design: complete and frozen on branch `docs/initial-frozen` (`d5cb413`);
  home-phase docs in `docs-local/`.
- Git remote `origin` = private GitLab (`mmz-personal/capstone-project`); owner
  pushes (`main` + `docs/initial-frozen`).

## Previous Session Summary

Session 18 (2026-09-09) — **Phase 4 increment 1 correction**:
- Owner identified `StorySummary.quality_class` as an evaluation-oracle leak:
  real Azure DevOps stories do not know their expected review outcome.
  Owner approved the resulting design-contract correction.
- `quality_class` removed from the authoritative `StorySummary` and inherited
  `StoryDetail`, so it cannot appear in API/MCP results; the strict public
  models explicitly reject it. Dataset `scenario` and expected contracts stay
  evaluation-only. `shared/review_schemas` bumped 0.2.0 → **0.3.0**.
- Phase 4 mapping plan, D9 amendment 4, D9 amendment 5 (decision record), and
  Runbook 10 updated to remove the stale mapping. No environment action; Cloud
  SQL remained STOPPED/NEVER.
- Independent read-only review: first pass found the missing direct
  `StoryDetail` rejection test and stale docstring; both fixed. Follow-up:
  **Ready to proceed**, no findings.
- Committed as `9950ae9` (docs-only) and `20ccd90` (implementation + local
  records). The docs commit was cherry-picked to `docs/initial-frozen` as
  `5307b70`; no push was performed.

Session 17 (2026-09-09) — **Phase 4 opened** (plan + increment 0):
- **Frozen-branch reconciliation check** (prior next-step 0): full-tree diff
  `docs/initial-frozen main -- docs/` shows exactly one divergence — the
  `docs/index.md` docs-local pointer from `c5dc040`. Owner decision: leave
  it (home-phase cross-reference, not design). Both branches pushed by owner.
- **Phase 4 plan written**: `docs-local/plans/phase-4-mcp-servers.md`
  (increments 0–5; commit `cf48512`).
- **Increment 0 done (test-first, commit `6452b15`)**:
  `shared/review_schemas` 0.2.0 — `StoryComment` + `ContextStory` added to
  `StoryDetail` exactly per schemas.md (code catching up to the session-16
  design change); re-exports + package-install test updated (that test pins
  version AND exact `__all__` — same-change update required).
- **Owner decisions recorded (D9 amendment 4, local-decisions.md)**:
  `StoryComment.author` KEPT (maps the anonymized persona; no docs change);
  preparation at SERVER STARTUP in memory (HTML flattening + ADO→StoryDetail
  mapping table; images dataset-agnostic; golden snapshots pin output);
  PDF library deferred to increment 3.
- **Runbook 10 opened** (`docs-local/runbooks/10-mcp-servers.md`) with
  increment-0 evidence + gotchas; `docs-local/runbook.md` evidence log
  updated.
- **Independent read-only review** of increment 0: Ready to proceed,
  0 Critical/Important, 1 Minor (runbook test-count wording) — fixed.

Session 16 (2026-09-09, two parts) — Phase 3 CLOSED (completion review
Ready-to-close, 3 Minor doc-drift fixed) + dataset extensions session
(comments + linked context stories: docs/ design changes, dataset structure
codified, comments API spike, 3 t1-only comment stories authored end-to-end
incl. expected files + manual plans, 45 stories / 36 tests green). Detail in
Runbooks 08–09 and git history.

Session 15 (2026-09-08) — Runbook 09 **increments 3 + 4 DONE — runbook
COMPLETE** (phase-completion review pending). Increment 3: expected files
authored from `dataset/manual-plans/`, first as 42 per-template files, then
**collapsed (owner decision) to 7 scenario-canonical files**
`dataset/expected/<scenario>.json` — the loader expands each to the 6
per-template test cases (format invariance enforced structurally; D9
amendment 2). Owner-approved decisions recorded: `story_id` = `story-01`…
`story-42` template-major (emitted by export_ado.py; envelopes carry it);
`expected_findings` = semantic stubs (runtime finding IDs not pinned);
`expected_turns` includes turn 1; conflicting closing = variant 1
(2-turn conversational finalize). `facilitator_turn_count` excludes PO
acceptance turns per schemas.md (clean=1 … unresolvable=10/park).
Unresolvable turns 2–9 deliberately routing-unpinned. Increment 4
(test-first, 23 red tests → 28 green): `dataset/loader/` uv package
(`dataset-loader`) — strict `StoryEnvelope` + `ExpectedCase` models
(vocabulary reused from `shared/review_schemas`), scenario→case expansion
(42 cases), dataset invariants; `make dataset-test` (28 passed) +
`make review-schemas-test` still green (147). `export_ado.py` now fetches
via **REST with `$ADO_PAT`** when set (WIQL + `workitems/{id}?$expand=all`;
az CLI fallback) — verified by a full REST re-export: all 45 files
content-identical to the az export. Data fix caught by tests: `C-r1`→`C-1`
in unresolvable.json. Owner decisions: story files keep stable key order
(envelope field order documented, work_item keys sorted — re-export of
unchanged data diffs only exported_at; the exported_at-only re-export was
reverted to keep the commit clean). Independent read-only review of
increment 4: **Ready to proceed**, 0 Critical/Important, 8 Minor — all
fixed same session (env guards, URLError catch, po_accepted-requires-
finalized + reports==requested_formats validators, plain-loop expansion,
narrowed pytest.raises, top-level test imports, 5 extra negative tests).
Also **Runbook 08 REST-equivalence increment** (owner-driven): az CLI auth
does NOT transfer to REST with an MSA login (AADSTS500011) — external auth
path is a **PAT** (owner-created `rest-verify`, Work Items: Read, in
gitignored `ado.env` as `ADO_PAT`; retained for re-exports — owner may
revoke/rotate, export falls back to az); single-GET `$expand=all` is
byte-equivalent to the az export; `workitemsbatch` interchangeable
(drops only internal fields); `workitems?ids=` returns fields at 7.1 but
no relations.

Session 14 (2026-09-07/08) — Phase 2 accepted; Phase 3 opened; ADO sample env;
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

Session 18:
- Test-first: focused `StorySummary` rejection test failed red as expected
  (`DID NOT RAISE ValidationError`); implementation then made it green.
- `make review-schemas-test`: **152 passed** (including public
  `StorySummary` and `StoryDetail` rejection coverage, clean-install/version
  assertion); `make dataset-test`: **36 passed** (one pre-existing Pydantic
  deprecation warning for loader `Field(unique=True)`). `git diff --check`
  passed.
- Independent read-only review: first pass **Needs fixes** (1 Important:
  `StoryDetail` rejection coverage; 1 Minor stale docstring), both fixed;
  follow-up **Ready to proceed**, no findings.

Session 17:
- `make review-schemas-test`: **151 passed** (147 + 4 new behavior tests,
  red-first ImportError on `ContextStory`); `make dataset-test`:
  **36 passed** (untouched).
- Independent read-only subagent review of increment 0: **Ready to
  proceed**, 0 Critical/Important, 1 Minor (runbook test-count wording,
  fixed same session).

Session 16:
- Extension authoring: `make dataset-test` **36 passed** (42→45 counts,
  matrix core-grid + t1-only, t1-only validator, 4 stale-count tests
  updated); `make review-schemas-test` **147 passed** (untouched);
  expected files 10/10 validate; post-export identifier checks clean
  (before commit); 42 pre-existing story files byte-stable (exported_at
  diffs reverted).
- Spec review (pre-authoring, independent read-only): Not-ready → 2
  Important fixed; spike evidence in Runbook 08.
- Phase 3 close-out: completion review Ready-to-close, 3 Minor doc-drift
  fixed; suites 28 + 147 at close time.

Session 15:
- `make dataset-test`: **28 passed** (23 written red-first + 5 added after
  review); `make review-schemas-test`: **147 passed** (untouched).
- REST re-export verified content-identical to the az export across all 45
  files (programmatic semantic diff); exported_at-only changes reverted
  before commit per owner decision; identifier checks clean.
- Independent read-only subagent review of increment 4: **Ready to
  proceed**, 0 Critical/Important, 8 Minor — all fixed and re-verified
  same session (evidence in Runbook 09).

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

- ~~Phase 3 close-out~~ DONE (session 16): completion review Ready-to-close,
  3 Minor fixed, phase marked done in development-plan.md. Deferred D9 items
  still open: fidelity/trimming (decide at Phase 4 against the verbatim
  export) and metadata semantic/display classification (now forced by the
  comments extension).
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

1. **Phase 4 increment 1 — story MCP server** (plan
   `docs-local/plans/phase-4-mcp-servers.md`): preparation module
   (envelope → `StoryDetail` per the corrected D9-amendment-4 mapping table,
   with dataset `scenario` never mapped or returned; HTML flattening, golden
   snapshots over all 45 files), then `list_stories` /
   `get_story` tools with spike-pattern auth wiring, error taxonomy,
   Dockerfile (copies `dataset/stories/` only). Test-first per increment.
2. Phase 4 increments 2–5 follow the plan (artifact → report → compose →
   Cloud Run deploy/smoke; Runbook 10 accumulates evidence).
3. Extension 2 (linked context stories) mock data — deferred by owner;
   structure is codified; authoring later is pure data preparation.

## Important Notes

- **Commit granularity for `docs/`**: commits touching `docs/` must be
  separate and atomic (never mixed with code/dataset/`docs-local/` changes)
  so they can later be cherry-picked onto `docs/initial-frozen` (owner rule,
  session 15; also recorded in the extensions plan).
- Deployment pipeline stance: none yet — local scripts + runbook only;
  pipelines written at promotion (local-decisions.md D3).
- Git: `main` is **6 ahead of origin** after session 18 (docs correction
  `9950ae9`, implementation `20ccd90`, plus four prior commits); the owner
  must push it. `docs/initial-frozen` is **1 ahead of origin** with the
  cherry-picked docs correction `5307b70`; the owner must push it too. The
  sole accepted prior divergence remains the `docs/index.md` docs-local
  pointer from `c5dc040`.
  Session-16 cherry-picks: `dfbde69`, `7b9975d`, `a787dbe` (hidden-conflict
  row rode along — correct content-wise). Old history note:
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
