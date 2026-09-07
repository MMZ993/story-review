# Runbook 09 — Phase 3: mock dataset (`dataset/`)

Implements `docs-local/plans/phase-3-mock-dataset.md` against
`docs/quality/mock-data.md`. Local-only phase: no GCP access, no Terraform,
no Cloud SQL (the instance stays STOPPED throughout). Prerequisites (az CLI,
ADO sample org/project, backlog authoring, export) are codified in
Runbook 08.

Status: IN PROGRESS (opened 2026-09-07; increment 1 blocked on the Runbook 08
export).

## Scope

- `dataset/stories/` — Azure DevOps work-item-export-shaped story files.
- `dataset/expected/` — expected-file contracts per mock-data.md.
- Trivial loader/validation harness + test suite (`make dataset-test`).
- Phase-completion gate: re-run `make dataset-test` and
  `make review-schemas-test`; independent read-only review.

## Dependencies on Runbook 08

- az CLI installed and signed in (`az login --allow-no-subscriptions`).
- Free ADO org + sample project (Agile template) with epics, the six scenario
  stories, tasks, sprints, area paths — authored via CLI where practical.
- The JSON export with relations expanded — the dataset ground truth.

## Increments

| # | Scope | Status |
|---|---|---|
| 0 | ADO sample environment, backlog authoring, export | Runbook 08 |
| 1 | Format ground truth, conventions, D9 decision, README | BLOCKED (Runbook 08 export) |
| 2 | Story authoring (six scenarios) | pending |
| 3 | Expected-file authoring | pending |
| 4 | Loader harness + validation tests (test-first), Make target | pending |

## Evidence

(to be appended per increment)
