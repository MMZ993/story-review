# Phase 3 — Mock dataset plan

## Objective

Author the single mock dataset (`dataset/stories/` + `dataset/expected/`) that
serves both the integration/evaluation tests and the live demo, per
`docs/quality/mock-data.md`. The dataset is a local-only, no-cost increment:
no GCP access, no Terraform, Cloud SQL stays STOPPED.

## Key design input — Azure DevOps export format (owner decision, session 11)

The story files must mirror, as closely as practical, a real Azure DevOps work
item export so the backlog shape is realistic. Ground truth comes from a free
Azure DevOps organization (Basic plan, free for ≤5 users) with a sample project
containing epics, stories, and tasks; the owner exports via a saved query →
JSON (or the REST API `wit/workitems` / `az boards`). Known shape from the
official REST docs (Work Items - List, api-version 7.1):

```jsonc
{
  "id": 1234,
  "rev": 3,
  "fields": {
    "System.WorkItemType": "User Story",
    "System.Title": "...",
    "System.Description": "<p>HTML</p>",
    "Microsoft.VSTS.Common.AcceptanceCriteria": "<p>HTML</p>",
    "System.State": "New",
    "System.AreaPath": "SampleProject\\Team",
    "System.IterationPath": "SampleProject\\Sprint 1",
    "System.Tags": "mock; payments"
  },
  "relations": [
    { "rel": "System.LinkTypes.Hierarchy-Reverse", "url": ".../workitems/1230" }
  ],
  "url": "https://dev.azure.com/..."
}
```

Decision points once the real export is in hand (record as a local decision,
expected `docs-local/local-decisions.md` D9):

- **Fidelity level**: keep ADO field names/HTML verbatim inside the dataset
  (dataset = export artifact), and let the story MCP server (Phase 4) translate
  to internal schema — vs. normalizing at authoring time. Working assumption:
  keep the export shape verbatim; translation belongs to the MCP server. The
  server is the "mock data store" boundary that already exists in the design.
- **Trimming**: drop or stub ADO-only noise (`url`, `rev`, identity fields) or
  keep them for realism; keep `relations` (parent links → epic context,
  hierarchy-Forward → tasks) since mock-data.md requires epic/roadmap context.
- **HTML**: rich-text fields are HTML in ADO; decide whether the dataset keeps
  HTML and Phase 4 flattens it, or the dataset stores the export verbatim and
  expected files reference the plain-text projection. Working assumption:
  dataset keeps export verbatim.

## Preconditions

- Phase 2 complete and re-reviewed (Runbook 07 status COMPLETE, suite 147
  passed post-review).
- **Increment 0**: local `az` CLI via mise + the free Azure DevOps sample
  organization + sample project, per Runbook 08
  (`docs-local/runbooks/08-azure-devops-sample-env.md`). Owner-created org
  (browser-only), CLI-managed backlog.
- **Blocking precondition for increment 1**: owner exports sample work items
  (epic + stories + tasks + sprint iteration paths) from the sample project —
  nothing is authored against the format before this lands, to avoid rework
  against a guessed shape.
- Cloud SQL remains paused. Phase 3 must not run `make db-resume`.

## Deliverables

```text
dataset/
├── README.md                    # format provenance, how the export was produced, license note
├── stories/                     # ADO work-item export JSON (per-story or single export file)
└── expected/                    # <case>.json expected-file contracts per mock-data.md
```

Plus a trivial loading/validation harness (location decided in increment 4 —
candidates: `dataset/tools/` or inside the future Phase 4 MCP server skeleton;
keep it out of any runtime image concern; expected files are excluded from
runtime images per repository-layout.md — enforce that later in Phase 4).

## Expected-file contract (from mock-data.md, unchanged)

Each `dataset/expected/<case>.json`: `story_id`, dataset schema version,
`po_script` (each turn exactly one of `message` or `po_accepted: true`),
`expected_turns` (DelegationDecision, outcome, session state, artifact
perspectives, turn_number), `expected_findings`, `expected_final`.

## Scenario coverage (one story per type, minimum)

| # | Type | Expected arc |
|---|---|---|
| 1 | Clean | both reviews positive; `ready` quickly |
| 2 | Business-weak | business gaps, engineering solid |
| 3 | Engineering-weak | missing edge cases/dependencies, business solid |
| 4 | Conflicting | findings contradict; synthesis flags; PO resolves via dialogue |
| 5 | Partial-resolution | one side resolved; re-review; new conflict on other side |
| 6 | Unresolvable | loop safety cap; facilitator parks the story |

Stories must be plausible, consistent backlog items (epic context, acceptance
criteria, tasks where the scenario warrants) — the same stories drive the demo.

## Implementation increments

### 0. Sample Azure DevOps environment (Runbook 08)

1. `mise use -g azure-cli@latest`; `az login --allow-no-subscriptions`; set
   `az devops` defaults (`$ADO_ORG`, `$ADO_PROJECT` in gitignored env file).
2. Owner creates the free org + sample project (Agile process template) in the
   browser; verify from CLI.
3. Author the backlog structure via CLI: sprints/iterations, epic(s) with
   roadmap context, the six scenario stories, tasks where warranted, hierarchy
   links; freeze a reproducible query.
4. Export to JSON with relations expanded — this is the dataset ground truth
   (also the deliverable of increment 1).

### 1. Format ground truth + dataset conventions

1. Inspect the export from increment 0; finalize the fidelity/trimming/HTML
   decisions above; record them as D9 in `docs-local/local-decisions.md`.
2. Write `dataset/README.md` documenting the export provenance and the
   conventions; create `dataset/stories/` and `dataset/expected/`.

### 2. Story authoring

1. Author the six scenario stories (+ epic/roadmap context items, tasks where
   warranted) as ADO-export-shaped JSON, using IDs/paths consistent with the
   sample project.
2. Backfill is inherent: increment 0 authors the stories directly in the ADO
   project and `dataset/stories/` is the genuine export of them.

### 3. Expected-file authoring

1. Author `dataset/expected/<case>.json` per the contract, tracing each PO
   script turn-by-turn against `docs/design/schemas.md` (TurnRequest exactly-one
   rule, DelegationDecision, session states, park-at-10 cap, finalization,
   report formats) and `docs/design/example-interaction.md` for dialogue shape.
2. Cross-check `docs/quality/evaluation-tests.md` deterministic-assertion
   requirements so expected files carry everything the Phase 9 runner needs.

### 4. Loader harness + validation tests (test-first)

1. First write failing tests, then a minimal harness that:
   - loads every story file and validates the ADO-export shape (a small
     Pydantic model for the export envelope, strict like `review_schemas`);
   - loads every expected file and validates its fields against installed
     `review_schemas` types where they map (the expected contract uses schema
     vocabulary even if it is not itself a Phase 2 model);
   - enforces dataset invariants: every expected case references an existing
     story; exactly-one-of in `po_script`; turn numbering consistency; all six
     scenario types covered.
2. Make target for the suite (e.g. `dataset-test`), using `uv` locks per
   project convention.

## Verification gates

```bash
make dataset-test          # after increment 4
make review-schemas-test   # still green (no schema changes expected; any need = design stop)
```

Phase-completion: expected files validate against Phase 2 schemas; stories load
through the trivial harness; independent read-only review of the dataset and
expected files (contract boundary, same as Phase 2); evidence in Runbook 09.

## Exit criteria (from development-plan.md)

- Expected files validate against the Phase 2 schemas.
- Stories load through a trivial harness.
- Evidence recorded in Runbook 09; Cloud SQL remains stopped.

## Out of scope

- MCP servers, Compose, Docker, Cloud Run (Phase 4).
- Agents, prompts, orchestration, TUI (Phases 5–7).
- Any infrastructure change.
- The judge / evaluation runner itself (Phase 9) — but expected files must not
  preclude its deterministic assertions.

## Risks and controls

| Risk | Control |
|---|---|
| Guessed ADO format diverges from reality | Increment 0 exports from a real org before anything is authored. |
| Expected files encode behavior that Phase 5/6 agents cannot actually produce | Trace every expected turn against schemas.md + example-interaction.md now; revisit at Phase 6 integration with dataset-version bump if needed. |
| HTML/verbatim ADO fields leak into runtime images | Dataset keeps export shape; runtime-image exclusion is enforced in Phase 4 (repository-layout.md). |
| Dataset scope expands into tooling work | Harness stays a trivial loader + validator; no server, no query engine. |

## References

- `docs/quality/mock-data.md` — authoritative dataset contract.
- `docs/quality/evaluation-tests.md` — downstream deterministic assertions.
- `docs/design/schemas.md`, `docs/design/example-interaction.md` — trace targets.
- `docs/operations/repository-layout.md` — dataset/versioning/image-exclusion rules.
- `docs-local/plans/phase-2-shared-schemas.md` — plan pattern this follows.
