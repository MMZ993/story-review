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

- Manual test plans authored (2026-09-07, session 13, owner-approved shape):
  `dataset/manual-plans/` — README (index, format-invariance rule, how-to-run)
  + one plan per scenario, keyed by scenario (not story id) so every future
  T2–T6 rendering must pass the same plan: clean (id 5, 2 turns),
  business-weak (id 10, 3 turns, business-only delegation),
  engineering-weak (id 14, 3 turns, engineering-only delegation),
  conflicting (id 17, 2 turns, conversational resolution, no delegation;
  2-vs-3-turn closing variant documented, variant 1 chosen),
  partial-resolution (id 18, 3 turns, transcribed from
  example-interaction.md), unresolvable (id 19, 10 turns, park at the loop
  safety cap; turn count may vary ±1 but park outcome is invariant),
  hidden-conflict (id 20, 2 turns, both reviews positive + C-1 at synthesis
  with zero per-perspective findings). Plans are the authoring source for
  increment 3's `dataset/expected/<case>.json` (mechanical transcription —
  same vocabulary). This also settles the deferred decision: expected files
  are keyed by canonical-case (scenario), not by ADO work-item id.
