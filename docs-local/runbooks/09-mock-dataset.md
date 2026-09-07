# Runbook 09 — Phase 3: mock dataset (`dataset/`)

Implements `docs-local/plans/phase-3-mock-dataset.md` against
`docs/quality/mock-data.md`. Local-only phase: no GCP access, no Terraform,
no Cloud SQL (the instance stays STOPPED throughout). Prerequisites (az CLI,
ADO sample org/project, backlog authoring, export) are codified in
Runbook 08.

Status: IN PROGRESS (opened 2026-09-07; increments 0–2 done — matrix
authored in Runbook 08; increment 1 done 2026-09-08; next: increment 3).

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
| 1 | Format ground truth, conventions, D9 decision, README | DONE (2026-09-08) |
| 2 | Story authoring (six scenarios) | DONE (Runbook 08, matrix T1–T6) |
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
  are keyed by canonical-case (scenario), not by ADO work-item id — now
  formalized as **D9** in `docs-local/local-decisions.md`: ADO ids are
  temporary authoring references; the export script re-keys stories to
  canonical case ids (ADO id kept only as marked provenance, e.g.
  `ado_source_id`); the story MCP serves from the exported JSON — locally
  from files, in the hosted demo from a Google-hosted mock endpoint standing
  in for a real ADO connection (fetch path identical, only the backing
  endpoint differs).
- [x] Increment 1 — export + conventions (2026-09-08, session 14,
      owner-approved): `dataset/tools/export_ado.py` exports all 42 stories
      + 3 context items into `dataset/stories/` (`t1`–`t6` per-template
      folders + `context/`), re-keyed to case ids `<template>/<scenario>`
      with the ADO id demoted to `ado_source_id` provenance. Envelope:
      schema_version, case_id, template, scenario, ado_source_id,
      exported_at, `work_item` (verbatim, HTML fields as-is). Resolution:
      template from `System.AreaPath`, scenario from the provenance ids in
      canonical-facts.md (T1–T4, T6) + t5-enabler-spec.md (T5); loud aborts
      on unknown/missing/duplicate/mismatched ids; counts asserted (42+3).
      Sanitization: `_links` dropped recursively; URL strings rewritten to
      `$ADO_ORG`/`<project-id>` placeholders (org name and project GUID
      leak via imageUrl/relation/url fields — caught by post-export check);
      author identity objects reduced to `Story Author` /
      `<author>@example.com` with account ids (id/descriptor/url/imageUrl)
      dropped — owner decision after the owner email was caught by the
      identifier check (personal data stays out of git / the public mirror).
      Owner decisions: export VERBATIM, preparation as a separate later
      step (no transform-on-export); `exported_at` in envelope. Recorded as
      the D9 amendment in local-decisions.md; `dataset/README.md` written
      (provenance, layout, conventions, license note). Post-export checks:
      45 files, zero `_links`/org-name/GUID/email/account-descriptor hits,
      envelope shape verified, T6/hidden-conflict description carries both
      capture statements.
      Gotcha: WIQL `az boards query --wiql` rows return the id as the sole
      value per row object.
