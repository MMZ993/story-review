# Runbook 08 — Azure DevOps sample environment (az CLI + free org)

Codifies the local `az` CLI setup and the free Azure DevOps sample organization
that produces the Phase 3 dataset ground truth (see
`docs-local/plans/phase-3-mock-dataset.md`, increment 0/1). Same spirit as
Runbook 01 (gcloud): identifiers stay in shell variables, evidence recorded at
the bottom.

Cost: none — Azure DevOps Basic plan is free for up to 5 users per
organization; no Azure subscription is needed for Boards. No billing
instrument is attached to the org.

Status: IN PROGRESS (opened 2026-09-07).

## 0. Identity conventions

All commands use shell variables. The org/project names are not secrets but
are kept out of git per the same convention as `$PROJECT_ID`; add to the
gitignored `infra/envs/home.env` (or a sibling gitignored file, e.g.
`infra/envs/ado.env` — decided in increment 1) :

```bash
source infra/envs/home.env        # existing
# ADO_ORG=...                     # dev.azure.com/<ADO_ORG>
# ADO_PROJECT=...                 # sample project name
```

## 1. Install az CLI (mise)

mise registry provides `azure-cli` (pipx backend), matching how gcloud is
managed on this workstation:

```bash
mise use -g azure-cli@latest     # add to global mise config and install
mise install                     # if adding by hand to config.toml instead
az version
```

Only the `devops` extension commands are needed; it ships built into modern az
versions. Verify:

```bash
az devops --help
```

Learned:
- `az devops` is NOT built into azure-cli 2.90.0 — it is the official
  `azure-devops` extension and triggers an interactive install prompt on first
  use. Codified as an explicit `az extension add` step (below) instead.
- mise installed it via the `uv tool install` backend (azure-cli@2.90.0) —
  note the shim also exposes Windows-style `az.bat`/`azps.ps1`; harmless.
- Iteration/area commands live under `az boards iteration|area project|team`,
  not `az devops admin` (which only has `banner` in 2.90.0).
- Work item IDs are ORG-wide and never reused, so IDs created in the deleted
  Basic project (the old epic took id 1) permanently offset the new project's
  IDs (Agile project starts at id 2). Cosmetic only; the dataset uses whatever
  IDs the export contains.
- `az boards iteration project create` `--path` demands an ABSOLUTE path with
  a leading backslash (`\$ADO_PROJECT\Iteration`), unlike `create --name`
  without `--path` (root level). Bash double quotes need `\\` per level.
- `az devops project list` prints an "Auto-detect ... no Azure DevOps remote"
  warning when the local git repo has no ADO remote — harmless; defaults from
  `az devops configure` apply.
- The fresh Microsoft account carries a **free-trial Azure subscription**
  ("Azure subscription 1") — it is NOT used: ADO Boards is free with no
  subscription, and no phase deploys Azure resources. Do not run any
  `az ... create` against it; only `az devops`/`az boards` commands are used.
- `az login --allow-no-subscriptions` still shows a tenant/subscription
  selection prompt when the tenant has subscriptions — press Enter (default);
  the DevOps token does not depend on the selection.

Explicit, prompt-free equivalent:

```bash
az config set extension.use_dynamic_install=yes_without_prompt
az extension add --name azure-devops
```

## 2. Sign in to Azure DevOps (interactive — browser/device code)

`az` login with a *Microsoft personal / work account* is enough for DevOps
(no Azure subscription required):

```bash
az login --allow-no-subscriptions     # no subscription to default to
az devops login --organization "https://dev.azure.com/$ADO_ORG"
```

`az devops login` is only needed for PAT-based stream commands (e.g.
`az repos`); most `az devops` commands take `--organization` directly and use
the az login token. Configure defaults to avoid repeating flags:

```bash
az devops configure --defaults organization="https://dev.azure.com/$ADO_ORG" project="$ADO_PROJECT"
```

Verify:

```bash
az account show                       # logged-in identity, no subscription
az devops project list --organization "https://dev.azure.com/$ADO_ORG"
```

## 3. Create the organization + sample project (mostly browser, one-off)

Org creation is a browser-only flow (no API/CLI) — owner action:

1. Sign in at <https://dev.azure.com> with the account; create a new
   organization (region: West Europe, closest).
2. Keep the free plan (Basic, 5 users). No Azure subscription required.
3. Create the sample project (private, Agile process template — gives User
   Story/Task/Epic hierarchy and the
   `Microsoft.VSTS.Common.AcceptanceCriteria` field), named per `$ADO_PROJECT`.

Then verify from CLI:

```bash
az devops project list --organization "https://dev.azure.com/$ADO_ORG" -o table
```

## 4. Author the sample backlog (mock data)

Order matters — parents first, then children, so hierarchy relations resolve:

1. Area path + iteration structure (sprints):

The Agile template pre-creates `Iteration 1..3` (unlike Basic's `Sprint 1`);
rename and date them (absolute paths need a LEADING backslash —
`\$ADO_PROJECT\Iteration\Sprint N` — and bash double-quote escaping
  `\\` per level):

```bash
az boards iteration project update --path "\\$ADO_PROJECT\\Iteration\\Iteration 1" \
  --name "Sprint 1" --start-date 2026-09-07 --finish-date 2026-09-20 \
  --org "https://dev.azure.com/$ADO_ORG" --project "$ADO_PROJECT"
# ... Sprint 2 (09-21..10-04), Sprint 3 (10-05..10-18) likewise
az boards iteration project list --project "$ADO_PROJECT" -o json
```

Verified fresh-Agile-project state (2026-09-07): work item types include
Epic/Feature/User Story/Task/Bug (user story carries
`Microsoft.VSTS.Common.AcceptanceCriteria`); area root single default. Note
from the owner's company backlog: real teams often keep acceptance criteria in
a description template instead of the dedicated field — our dataset uses the
dedicated field deliberately (schema-friendly, cleanly separable for the
Phase 4 MCP translation); recorded with the D9 decisions.

2. Epic(s) with roadmap context (description = the roadmap/why text the
   reviewers need), then the six scenario user stories under them
   (title, HTML description, HTML acceptance criteria, tags per the plan's
   scenario table), then tasks under stories where the scenario warrants
   (`az devops work item create ... --work-item-type ...`):

```bash
az devops work item create \
  --title "..." \
  --description "<p>...</p>" \
  --fields "Microsoft.VSTS.Common.AcceptanceCriteria=<p>...</p>" \
  --work-item-type "User Story" \
  --area ... --iteration ...
```

(Corrected after install: the command group is `az boards work-item`, and the
actual executed form was `az boards work-item create --title ... --type ...`.)

3. Link children to parents — `relation add` takes the friendly name `parent`
  and has NO `--project` flag (org only):

```bash
az boards work-item relation add \
  --id <child> --relation-type parent --target-id <parent> \
  --org "https://dev.azure.com/$ADO_ORG"
```

4. Freeze the backlog snapshot as a query, so the export is reproducible:

```bash
az devops query --wiql "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '$ADO_PROJECT' ORDER BY [System.Id]"
```

## 5. Export to JSON (dataset ground truth)

Per the Phase 3 plan, export with relations expanded (hierarchy = epic context):

```bash
az devops query --id <query-id> --output json > /tmp/ado-query.json          # query rows
az boards work-item show --id <id-list> --expand all --output json > dataset/stories/backlog.json
```

Learned: (append — exact shape of the CLI output vs REST, whether relations
are included, HTML handling; record the final export command as THE way to
reproduce the dataset).

## 6. Teardown (deferred)

The org is free and holds the reproducible dataset source; keep it until after
the capstone is graded. If needed later: delete project / delete org (owner,
destructive, browser-only).

Learned (dataset authoring, 2026-09-07):
- Owner decision: stories carry NO Effort/story points — the system's insertion
  point is pre-refinement/pre-estimation (stories are unestimated when
  reviewed). To be stated in `dataset/README.md`.
- Owner decision: info-level non-blocking findings allowed even on the clean
  scenario — expected files assert routing/decisions deterministically but
  tolerate finding prose ("loose enough to not break flows, tight enough to
  route").
- Owner decision: story templates are varied per team — `dataset/story-templates.md`
  defines T1-T5 as FORMATS (BDD, checklist, sectioned, classic user story,
  free text), deliberately decoupled from story QUALITY (well-filled → vague).
  System requirement under test: format invariance — same content through any
  template must yield the same review outcome; formatting at most info-level
  notes. Matrix: scenarios × templates (all six authored in T1 first), quality
  axis added in stress datasets. Deferred design input for Phase 5 agents:
  reviewers must assess from the description when the AC field is empty.
- Independent template review (subagent, 2026-09-07): 4 Important findings,
  all adopted into `dataset/story-templates.md` — (1) T5 re-scoped as a
  work-item TYPE variant, excluded from invariance assertions; (2) canonical
  content model: variants rendered from per-scenario canonical facts, not
  paraphrased from each other; (3) invariance asserted on normalized semantic
  grounds (finding codes/severity/readiness/decisions), not verbatim prose;
  (4) HTML/rich text split out as a separate ingestion-stress set (Phase 4).
  Minor findings adopted: T2 characterized as a field-location test; T6
  must-contain-all-canonical-facts rule; titles as rendering targets. Deferred
  to Runbook 09/expected-file design: canonical-case ID in the expected
  contract; metadata semantic/display classification. Extra templates and the
  semantic-vs-usability measure split noted as considerations only.
- `az boards work-item update --id N --fields "System.Tags=a; b"` for tags;
  ADO returns tags alphabetically sorted. Note: `work-item update` does NOT
  accept `--project` (unlike `create`) — org flag only. Flat-list queries are
  `az boards query --wiql ...` (not `az devops query`), and `System.Parent`
  is not returned unless explicitly projected — verify parents via
  `work-item show --expand all` relations instead.
- Owner decisions on backlog realism (2026-09-07): stories are reviewed in the
  BACKLOG, pre-estimation/pre-sprint; descriptions are FREE-FORMAT per team
  (no unified template — dataset must not force one); task work items vs the
  same information in the description are equivalent for reviewers (Phase 4
  MCP translation treats both as story context — record with D9).

## Evidence

- [x] mise: `azure-cli@2.90.0` installed globally (uv tool backend),
      `az version` OK (2026-09-07, owner-run).
- [x] `azure-devops` extension installed (owner-run, prompted Y on 2026-09-07);
      `az devops -h` OK — subgroups admin/project/security/team/wiki + related
      `az boards` (work items, queries) present.
- [x] Signed in (`az account show` OK 2026-09-07 — identity confirmed, no
      subscription usage; free-trial subscription present but unused).
- [x] devops defaults set (`az devops configure` OK; `$ADO_ORG`/`$ADO_PROJECT`
      in gitignored `infra/envs/ado.env`).
- [x] Org created (browser, 2026-09-07): `$ADO_ORG` = free Basic plan,
      West Europe, no Azure subscription linked. Project creation next.
- [x] First project accidentally created with **Basic** process (types:
      Epic/Issue/Task — no User Story/Feature, no Acceptance Criteria field).
      Base process is immutable per project; owner deleted and recreated
      `story-review` with **Agile** (verified: Epic/Feature/User Story/Task/Bug).
- [x] Sample project verified from CLI: `az devops project list` shows
      `story-review` (Private). Project ID <project-id>.
- [x] Structure (2026-09-07, agent-run with owner approval): Sprint 1-3
      renamed/dated (Iteration 1-3 template default); Epic id 2 "Payment
      Platform Expansion" (roadmap HTML description); Features id 3
      "Alternative Payment Methods" and id 4 "Checkout Reliability", both
      hierarchy-linked to the epic (verified: Feature 3 shows
      `System.LinkTypes.Hierarchy-Reverse` → 2).
- [x] Six scenario stories + tasks authored: CLEAN story (id 5) + 4 tasks
      (ids 6-9); BUSINESS-WEAK story (id 10) + 3 tasks (ids 11-13) — both
      Sprint 1, hierarchy verified (5 under Feature 4; 10 under Feature 3).
      ENGINEERING-WEAK story (id 14) + 2 tasks (ids 15-16) under Feature 4.
      Three scenarios remain (conflicting, partial-resolution, unresolvable).
- [x] Matrix decision (2026-09-07): scenarios × templates — all six authored
      in T1 first, later duplicated across T2-T5; ADO structure for the matrix
      (projects vs teams/areas) open, record with D9. `dataset/story-templates.md`
      created (T1-T5). Existing stories 5/10/14 rewritten into T1 form (short
      designation titles, Context/Reason/Scope descriptions, Given/When/Then
      criteria).
- [x] Task work items (ids 6-9, 11-13, 15-16) deleted (owner-approved,
      2026-09-07; recycle bin). Stories 5/10/14 are self-contained — verified:
      no children, parent links intact. Task content was already covered by
      each story's T1 criteria; a task-based template may return later as a
      separate matrix column. Gotcha: `az boards work-item delete` requires
      `--project` even with org set.
- [x] Owner correction (2026-09-07): stories live in the BACKLOG, not a sprint
      — review/estimation happens against the backlog, sprints are for already-
      ready stories. All stories moved to the root iteration
      (`$ADO_PROJECT`) = backlog; verified.
      sprint — review/estimation happens against the backlog, sprints are for
      already-ready stories. All stories + tasks (ids 5-16) moved to the root
      iteration (`$ADO_PROJECT`) = backlog; verified.
- [x] Remaining three T1 scenario stories authored (2026-09-07, agent-run with
      owner approval): id 17 CONFLICTING "Auto-select last used payment method
      at checkout" (tags checkout; payments; ux — business will flag auto-charge
      risk vs engineering flagging the one-page latency budget; findings
      contradict), id 18 PARTIAL-RESOLUTION "Save payment details for returning
      customers" (tags payments; saved-cards — deliberate mirror of
      example-interaction.md `story-04`: no consent/retention policy,
      "faster" unmeasured, wording implies raw storage), id 19 UNRESOLVABLE
      "Localize checkout for international customers" (tags international;
      localization; payments — undefined scope, no single owner, designed to
      never converge so the facilitator parks at the loop cap). All under
      Feature 3, backlog iteration, hierarchy links verified
      (Hierarchy-Reverse → 3 each), tags verified alphabetical. **T1 baseline
      column complete: 6/6 scenario stories (ids 5, 10, 14, 17, 18, 19).**
- [x] Scenario extension (2026-09-07, owner-approved): docs/quality/mock-data.md
      scenario table extended to a 7th row — HIDDEN-CONFLICT (both reviews
      individually positive, justifications rest on contradictory assumptions,
      synthesis flags). Story id 20 "30-minute order edit window after
      purchase" authored under Feature 4 (tags checkout; orders; support,
      backlog iteration, parent → 4 verified). Planted hooks: Context states
      "captures payment immediately at order placement" (engineering hook);
      Reason states "payment is only reserved… releasing the reservation is
      free" (business hook) — each innocuous alone, contradictory together.
      T1 baseline column is now 7/7 scenario stories (ids 5, 10, 14, 17, 18,
      19, 20).
- [x] Template-matrix areas (2026-09-07, owner-approved D9 structure): one
      project, one area path per template — `T2`–`T6` created at root via
      `az boards area project create --name` (T1 stays the root/default
      area; variants will sit under the same Features as their T1
      originals). Gotcha: `area project list` output is a nested tree —
      flatten with `jq '.. | .name? // empty'`.
- [x] T2 column authored (2026-09-07, session 13, owner-approved; drafted by
      subagent from the T1 stories per the canonical-fact rules in
      `dataset/story-templates.md`, drafts + must-retain/must-not-add lists
      in `dataset/drafts/t2/`; independent subagent review PASS + agent
      live-T1 cross-check: no fact loss, no additions, all planted gaps
      preserved — incl. both hidden-conflict capture statements, unreconciled).
      Ids 21–27 (clean 21, business-weak 22, engineering-weak 23,
      conflicting 24, partial-resolution 25, unresolvable 26,
      hidden-conflict 27), each in area `story-review\T2`, AC field empty
      (criteria live under "For this story:" in the description — the T2
      field-location test), same tags/titles as T1, parent links verified
      (21→4, 22→3, 23→4, 24→3, 25→3, 26→3, 27→4), backlog iteration.
- [x] Canonical fact document (2026-09-07, session 13):
      `dataset/canonical-facts.md` — one entry per scenario (facts, criteria,
      must-not-add = planted gap protection, title, provenance ids),
      assembled from the verified T2 must-retain lists. Linked from
      `story-templates.md`; the authoritative renderer input for T3–T6.
- [ ] Reproducible query saved.
- [ ] JSON export produced and shape recorded.
