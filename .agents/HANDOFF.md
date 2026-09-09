# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
Last updated: 2026-09-10 (session 25 CLOSED — `/healthz`→`/health` rename,
  Cloud Run redeployed, smokes green; commits pushed + frozen cherry-pick done).

## Where we are

- Phase: **4 — implementation COMPLETE** (increments 0–5 done; both exit gates
  green). Remaining for phase close: independent review + owner-approved
  commits/push. Then Phase 5 (agents + ADK adapters, `local-agents` compose
  profile).
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

Session 25 (2026-09-10, main PC; detail in Runbook 10 follow-up section):
- Owner-driven manual curl session against the deployed story service led to
  the discovery that **the Google frontend intercepts the literal path
  `/healthz` on `*.run.app` hostnames** (container logs proved exact-path
  requests never reach uvicorn; `/healthz/` → 307 did). Owner decision:
  rename the public health path to `/health`.
- Rename implemented test-first: `mcp-ingress` **0.1.1** (`PUBLIC_PATHS =
  {"/health"}` — version bump required: the story test target installs the
  package non-editable and uv served the cached 0.1.0 wheel), three servers'
  custom routes, Makefile compose wait, `tests/contract/conftest.py`.
- Redeployed: three images rebuilt/pushed (`20260909-180[12]-353f3b4`),
  image content verified pre-apply, owner-run targeted applies. Two apply
  gotchas hit and recorded in the runbook: (1) an image-update apply must
  also pass the `mcp_*_service_url` -vars or the audiences get wiped →
  fail-closed 503; (2) placeholder text pasted into `-var` values plans fine
  and fails at apply. All three smokes green on the new revision; manual
  `curl /health` → `{"status":"ok"}`; Cloud SQL stayed STOPPED throughout.
- `docs/design/api-contract.md` + `docs/operations/deployment.md` updated to
  `GET /health` (atomic docs commit; **cherry-pick to `docs/initial-frozen`
  pending — owner**).

Session 24 (2026-09-10, main PC — full cloud access; detail in Runbook 10 §5):
- Merged `dev-server/session-23` (increment 4) into main (merge commit);
  added repo-scoped ignore for `deploy/env/.env`; fixed runbook port-binding
  prose; created local `WORKING_ENVIRONMENT.md` per the new AGENTS.md step 0.
- **Phase 4 increment 5 COMPLETE (exit gate #2)**: `infra/modules/mcp-service`
  + three Cloud Run services (spike pattern: D8 ingress, ID-token audience
  fail-closed, two-step apply, min instances 0); storage-module fixes
  (report SA grants matched to the real `runs/` layout — D11, runs-tree
  lifecycle 90d, story-dataset bucket); `deploy/cloud-run/{story,artifact,
  report}/deploy.sh` + `.env.example`; `deploy/cloud-run/smoke/` + Makefile
  `mcp-*-deploy`/`mcp-*-smoke` (impersonated sa-orchestration ID tokens,
  sandbox-only tokenCreator grant via `smoke_user_email`); `make
  dataset-push` (48 objects). All three smokes green (story/artifact/report).
- Also fixed pre-existing Makefile bug: `dataset-push` used `guard-project`
  as a prerequisite (a recipe define) — would have failed.

Session 23 (2026-09-10, dev server — env-restricted session; detail in
  Runbook 10 §4):
- **Phase 4 increment 4 COMPLETE (exit gate #1)**: `deploy/docker-compose.yml`
  `local` profile (fake-gcs `-backend memory` + `gcs-init` bucket bootstrap
  gating artifact/report via `service_completed_successfully`; story on
  the mock source with `dataset/stories` bind-mounted ro; all host ports
  bound to 127.0.0.1; `*_AUTH_DISABLED=1` local-only),
  `deploy/env/.env.example`, real `make compose-up`/`compose-down`, new
  `make compose-contract-test`.
- **ADC-in-container gotcha fixed** (Runbook 10 §3 follow-up):
  `artifact_mcp/storage.py` now mirrors the report-server
  `AnonymousCredentials`-when-endpoint-set pattern; test fixtures in
  artifact/report suites also fixed (masked on the main PC by working
  ADC — red 32/26 errors on this ADC-less machine → green). Story server
  unaffected (compose uses the mounted directory; `gs://` is
  Cloud-Run-ADC only).
- **Cross-service contract suite** `tests/contract/` (20 tests, real
  streamable HTTP, no ASGI stand-in): tool matrices, dataset serving,
  error taxonomy over the wire, artifact idempotency incl. across
  `docker compose restart artifact`, report render md/pdf from a
  live-saved finalized-review, shared-bucket prefix contract
  (`runs/<run>/reports/` vs `runs/<run>/artifacts/`).
- Increment-4 review: first pass Ready-to-proceed with 1 Important
  (0.0.0.0 exposure) + 4 Minors — all fixed and re-verified green.
- Session ran on the dev server (no cloud access): checkout synced via
  owner-approved `git pull --rebase` (local AGENTS.md commit → `9441ef8`).

Session 22 (2026-09-10) — **Phase 4 increment 3 COMPLETE** (detail in
  Runbook 10 §3):
- **Owner decisions** (settled in chat, pre-code): PDF library = **fpdf2**
  (determinism + image size); auth middleware **extracted now** into
  `shared/mcp_ingress/` (package `mcp-ingress` 0.1.0 — story/artifact
  `auth.py` copies were diff-identical, deleted, servers/Dockerfiles/
  Makefile rewired; new `make mcp-ingress-test`); report server uses its
  **own storage module on the same artifact bucket** with disjoint
  prefixes (no MCP-over-HTTP hop).
- **Report MCP server** `mcp_servers/report/` (uv package `report-mcp`
  0.1.0): `render.py` (FinalizedReview → blocks → deterministic MD/PDF;
  pinned CreationDate, no /ID trailer, latin-1 PDF divergence documented),
  `storage.py` (reads `runs/<run>/artifacts/<id>.json`, writes
  `runs/<run>/reports/…`; claim-before-write idempotency per (run, format),
  key payload pins finalized-review id+checksum → different reference =
  `IDEMPOTENCY_KEY_REUSED`; orphan-key and content/meta two-write crash
  windows both recoverable; caller checksum verified against stored
  record), `server.py` (single orchestration-only `render_report`),
  `errors.py` (RENDER_FAILED for fpdf2 errors; internal errors
  non-retryable), `app.py`/`main.py` (`REPORT_*` env, bucket validated at
  build, `AnonymousCredentials` when `REPORT_GCS_ENDPOINT` set).
- Dockerfile + `make mcp-report-test` (fake-gcs :9024). Container smokes
  passed incl. a real render_report PDF round trip over HTTP with
  idempotent retry.
- **Increment-3 review**: first pass Needs fixes (1 Important:
  `_write_report` two-write crash window made retries permanently stuck) —
  fixed with checksum-verified tolerance + orphan regression test; 5
  Minors fixed; follow-up review **Ready to proceed**.
- **Gotchas recorded**: story/artifact servers share the ADC-in-container
  gap (healthz-only smokes hid it) — MUST be fixed in compose increment 4
  (same one-line `AnonymousCredentials` change); fake-gcs must publish on
  0.0.0.0 for cross-container access.

Session 21 (2026-09-10) — **Phase 4 increment 2 COMPLETE** (detail in
  Runbook 10 §2):
- **Artifact MCP server** `mcp_servers/artifact/` (uv package
  `artifact-mcp` 0.1.0): `GcsArtifactService` over google-cloud-storage
  with injectable endpoint (fake-gcs-server locally, real GCS in Cloud
  Run — same code path). Object layout `runs/<run>/artifacts/<id>.json`
  + `runs/<run>/idem/<type>/<key>`; generation-0 preconditions for
  immutability; **claim-before-write** idempotency (crash window →
  orphaned key, retry fills the record, no duplicate versions);
  (type, perspective, version) ordering + pagination + `is_latest`.
- `server.py` (mcp 2.1.1 `MCPServer`; tools `save_artifact`/
  `get_artifact`/`list_artifacts`; per-tool allowlists via `CallerRoles` —
  save orchestration-only, reads + facilitator; input validation
  `strict=False` because wire UUIDs are strings), `errors.py`
  (ARTIFACT_NOT_FOUND / IDEMPOTENCY_KEY_REUSED non-retryable;
  PreconditionFailed retryable; internal errors non-retryable),
  `auth.py`/`app.py`/`main.py` (spike pattern, `ARTIFACT_*` env;
  fail-closed allowlists; `ARTIFACT_BUCKET` validated at build).
- Dockerfile (no dataset + guard); container healthz smoke OK against
  fake GCS. New `make mcp-artifact-test` (starts fake-gcs-server in
  Docker on :9023, readiness-checked, tears down after).
- **Increment-2 independent review**: first pass Needs fixes (3 Important:
  lost-race idempotency poisoning, claim/record crash window, retryable
  internal errors) — all fixed same session with regression tests;
  minors fixed (docstring env name, isinstance PreconditionFailed, five
  ported ingress tests, readiness failure, bucket validation) or
  documented in code (full-record downloads per list/save; serialized-
  writer version assumption; auth middleware still a story copy —
  extraction candidate at increment 3).

Session 20 (2026-09-10) — **Phase 4 increment 1 COMPLETE** (see Verification
  and Next Steps below; detail also in Runbook 10):
- **`shared/ado_wire` extraction (D9 amendment 6, commit `23b2ab1`)**:
  cheap-model subagent assessed first (tests-untouched hypothesis held),
  implementation subagent did the split move — `WorkItem`/`WorkItemComment`
  (verbatim) to new shared package `ado-wire` 0.1.0 (pydantic only);
  `StoryEnvelope` + dataset aliases stay in `dataset_loader`, which
  re-exports the moved models. All existing test dirs byte-identical. New
  `make ado-wire-test` (7 tests).
- **Story MCP server (commit `b2124be`)**: `backlog.py` (id spaces
  `story-NN`/`ado-N`, status filter, source resolution), `mock_source.py`
  (directory or `gs://` location, in-memory prep at startup, fail-loud),
  `azure_source.py` (live ADO REST: PAT, WIQL + workitemsbatch +
  `$expand=all` + comments; `httpx.MockTransport` fixtures, no network in
  tests; 404→STORY_NOT_FOUND, transient→UPSTREAM_UNAVAILABLE retryable),
  `errors.py` (ToolError payloads, correlation id from `X-Correlation-Id`),
  `server.py` (mcp 2.1.1 `MCPServer` — FastMCP was renamed; tools
  `list_stories`/`get_story` with flat schemas matching the shared models;
  unknown-field rejection via raw call arguments —
  `context.request_context.params["arguments"]` is a Mapping KEY; every
  failure = structured ToolError with is_error), `auth.py` (spike-pattern
  ID-token middleware, `/healthz` public, missing audience + auth on → 503
  fail-closed, `STORY_AUTH_DISABLED=1` local switch), `app.py`/`main.py`
  (env-driven stateless Streamable HTTP wiring). `prepare.py` extracted
  `prepare_work_item`/`context_story_from_work_item` cores
  behavior-identically (goldens stayed byte-stable). story-mcp 0.2.0.
- **Infra pieces**: Dockerfile (root context; ships `story_mcp`,
  `review_schemas`, `ado_wire`, `dataset/loader` code-only + build-time
  guard banning `dataset/stories`/`dataset/expected` content); container
  smoke over real HTTP passed (healthz + tools/list; bad location aborts
  startup loudly); `dataset/tools/push_dataset.py` + `make dataset-push`
  (48 objects: 45 stories + 3 context; `--dry-run` verified; bucket
  bootstrap stays at increment 5).
- **repository-layout.md amended** (owner decision a): Dockerfiles may copy
  the `dataset/loader` CODE, never dataset content — main `ad841b3`, frozen
  cherry-pick `2a29f71`.
- **Increment-1 independent review**: first pass Needs fixes (2 Important:
  allowlist fail-open on missing env; azure 404-vs-transient conflation) —
  both fixed same session with regression tests; minors fixed or accepted
  as-is (documented in Runbook 10). **Owner decision: Cloud Run deploys
  stay at increment 5 per plan (option 1); increments 2–4 local first.**
- Runbook 10: increment 1 part 1b + part 2 entries with evidence and mcp
  2.1.1 gotchas (commit `b938c3a`).

Session 19 (2026-09-09) — **Phase 4 increment 1, part 1: dual-source design +
preparation**:
- **D10 design change (owner-driven)**: story MCP server gets a dual data
  source — `azure` (production path: live ADO REST, WIQL + `$expand=all` +
  comments; reuse the `rest-verify` PAT from `ado.env`, Secret Manager at
  increment 5) and `mock` (frozen dataset published to
  `gs://$PROJECT_ID-story-dataset/` via `make dataset-push`; local tests use
  a directory location). Selection: deployment `STORY_SOURCE` +
  orchestration-only per-call override (option a, stateless server);
  `StoryId` widened `^(story-[0-9]{2}|ado-[0-9]{1,8})$`; evaluation runs
  always `mock`. Docs changed atomically, cherry-picked to frozen
  (`37309db`→`5ab7380`, `336ea8e`→`7eb9cec`); D10 recorded; phase-4 plan
  rescoped (bucket bootstrap + `dataset-push` at increment 1/5, images
  dataset-agnostic — supersedes D9-amendment-4 baked-image idea).
- `shared/review_schemas` **0.4.0** (test-first): `StorySource`, `source` on
  `ListStoriesInput`/`GetStoryInput`, widened `StoryId`.
- `mcp_servers/story/` uv package `story-mcp`: `flatten.py` (stdlib HTML
  flattener: strip tags, decode entities, block tags → line/item boundaries),
  `prepare.py` (owner-approved field-by-field mapping incl. `"Epic — Feature"`
  epic_context, epic-description roadmap_context, comments sorted by
  createdDate, linked_stories → ContextStory; scenario/template never
  mapped), 45 **golden snapshots** (`tests/golden/`, owner-reviewed once,
  `tests/generate_golden.py` regenerates on approved mapping change).
- New Makefile target `mcp-story-test`. No environment action; Cloud SQL
  stayed STOPPED/NEVER.
- Commits: `37309db`, `7521c81` (docs + docs-local), `336ea8e`, `61acc3f`
  (pattern tightening + schema 0.4.0), `542569f` (preparation + goldens).
  All owner-push pending (main +5, docs/initial-frozen +2).

Session 18 (2026-09-09) — **Phase 4 increment 1 correction**: owner
identified `StorySummary.quality_class` as an evaluation-oracle leak; removed
from public contracts (strict models reject it), `shared/review_schemas`
0.3.0, docs/plan/runbook/D9 amendments 4–5 updated; reviewed Ready-to-
proceed; commits `9950ae9` (→ frozen `5307b70`) + `20ccd90`. Detail in
Runbook 10 and git history.

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

Session 25:
- Test-first red confirmed in all four suites (401 / PUBLIC_PATHS mismatch),
  then green: mcp-ingress **7**, story **67**, artifact **32**, report **34**;
  compose rebuilt + `make compose-contract-test` → **20 passed**;
  `git diff --check` clean; identifier check on the diff clean.
- Cloud Run: all three smokes green post-redeploy (story/artifact/report);
  `make db-status` STOPPED NEVER at start and end; manual authed
  `GET /health` → `{"status":"ok"}` on all inputs.
- No independent review this session (small mechanical rename + docs;
  review threshold per development-rules not met — no schema/gate/security
  logic change beyond a public-path constant).

Session 24:
- terraform validate + fmt-check green; every apply owner-run on a reviewed
  targeted plan (Cloud SQL untouched throughout — stayed STOPPED).
- Smoke green on Cloud Run (sanitized evidence in Runbook 10 §5): story
  (45 stories + detail + STORY_NOT_FOUND), artifact (save/get roundtrip),
  report (md render from live-saved finalized review across both services).
- Independent read-only subagent review of the increment-5 diff: **Ready to
  proceed**; 1 Important (audience-as-plain-env deviation unrecorded → D12
  added) + 5 Minor — all fixed same session (smoke null-URL guards,
  smoke-script cleanups); all three smokes re-run green after the fixes.
- `make db-status` STOPPED at start and end; cost state: 3 Cloud Run
  services min-0, near-empty buckets. Added `make artifacts-purge`
  (owner-run, confirmation-gated) for dev hygiene; Cloud Run needs no
  up/down (scale-to-zero).

Session 23:
- Red→green for the gotcha fix: `make mcp-artifact-test` 32 errors
  (DefaultCredentialsError) → **32 passed**; `make mcp-report-test` 26
  errors → **34 passed** after fixture fixes.
- `make compose-up` → all three healthz 200, bucket pre-created;
  `make compose-contract-test` → **20 passed** (twice: before and after
  review fixes); `make compose-down` clean.
- Suites at close: review-schemas **154**, ado-wire **7**, dataset **36**,
  mcp-ingress **7**, mcp-story **67**, mcp-artifact **32**, mcp-report
  **34**, compose contract **20**. `git diff --check` clean.
- Independent review: Ready to proceed; 1 Important + 4 Minor all fixed
  same session (detail in Runbook 10 §4).

Session 22:
- Test-first (red confirmed: `ModuleNotFoundError: report_mcp`;
  mcp_ingress middleware tests written with the package).
- Suites at close: `mcp-report-test` **34** (7 render + 9 storage + 18
  server/ingress), `mcp-ingress-test` **7**, `review-schemas-test` **154**,
  `ado-wire-test` **7**, `dataset-test` **36**, `mcp-story-test` **67**,
  `mcp-artifact-test` **32**. `git diff --check` clean; Docker builds OK
  (report + rebuilt story/artifact with mcp_ingress); report container
  smoke: healthz + render_report PDF round trip + retry idempotency +
  missing-bucket abort, all over real HTTP against fake GCS.
- Increment-3 review (report server + extraction): first pass Needs fixes
  (1 Important, 5 Minor) → all fixed → follow-up **Ready to proceed**.
  Findings detail in Runbook 10 §3.

Session 21:
- Test-first per module (red confirmed: `ModuleNotFoundError: artifact_mcp`
  for storage tests, `artifact_mcp.app` for server tests).
- Suites at close: `mcp-artifact-test` **32** (14 storage + 13 server
  contract + 5 ingress), `review-schemas-test` **154**, `ado-wire-test`
  **7**, `dataset-test` **36**, `mcp-story-test` **67**. `git diff --check`
  clean; Docker build + container healthz smoke passed.
- Increment-2 review (storage + server): Needs fixes → fixed → re-verified
  (32 green incl. orphan-key and non-retryable-internal regression tests).
  Findings detail in Runbook 10 §2.

Session 20:
- Test-first per module (red confirmed: `story_mcp.backlog`/`mock_source`/
  `app` ModuleNotFoundError; azure fixture tests red on missing module).
- Suites at close: `review-schemas-test` **154**, `ado-wire-test` **7**,
  `dataset-test` **36**, `mcp-story-test` **67** (21 prep/golden + 10
  backlog + 7 mock-source + 9 azure-fixture + 20 server-contract).
  `git diff --check` clean; Docker build + container smoke passed.
- Increment-1 review (schema + server): Needs fixes → fixed → re-verified
  (67 green incl. two regression tests). Findings detail in Runbook 10.
- ado_wire refactor verified by the implementing subagent AND the main
  session (all four suites re-run independently).

Session 19:
- Test-first throughout: flattener red (`ModuleNotFoundError: story_mcp`),
  prepare red (`No module named 'story_mcp.prepare'`), schema red (missing
  `source` attr / `ado-5` rejected) — all for the intended missing behavior.
- `make mcp-story-test`: **21 passed** (flattener 11, mapping 9, golden 1);
  `make review-schemas-test`: **154 passed**; `make dataset-test`:
  **36 passed** (pre-existing pydantic `Field(unique=True)` warning only);
  `git diff --check` clean.
- Golden snapshots (45) reviewed and approved by the owner before commit.
- Identifier check on committed files clean (gotcha: unset `$ADO_ORG` made
  the first check a false all-files match — both env files must be sourced;
  recorded in Runbook 10).
- Independent review: deferred to the full increment-1 review (part 2).

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

1. **Phase 4 close**: phase completion review per development-plan (the
   increment-5 independent review is already done and green).
2. Phase 5 opens after Phase 4 close (agents + ADK adapters,
   `local-agents` compose profile).
3. Optional hardening candidate for a later increment: put the
   `mcp_*_service_url` audiences into `home.tfvars` so image-update applies
   cannot silently wipe them (runbook gotcha, session 25).

Session-25 pushes (owner, done): main `830e789`/`28b2774`/`2a7a5e6` pushed;
   `830e789` cherry-picked onto `docs/initial-frozen` and pushed.

## Important Notes

- **Commit granularity for `docs/`**: commits touching `docs/` must be
  separate and atomic (never mixed with code/dataset/`docs-local/` changes)
  so they can later be cherry-picked onto `docs/initial-frozen` (owner rule,
  session 15; also recorded in the extensions plan).
- Deployment pipeline stance: none yet — local scripts + runbook only;
  pipelines written at promotion (local-decisions.md D3).
- Git: session-22 increment-3 work committed as `d65eb1c` (feat: report
  mcp server + shared ingress middleware — includes a `.gitignore` addition
  for `__pycache__/`/`.pytest_cache/`, which had not been ignored);
  pushed by the owner (origin/main at `d65eb1c`). The owner's draft
  `docs-local/plans/future-extensions.md` committed separately as
  `b9afaef` (owner push pending). Check `git status -sb` before assuming the
  remote is current.
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
