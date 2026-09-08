# Runbook 09 — Phase 3: mock dataset (`dataset/`)

Implements `docs-local/plans/phase-3-mock-dataset.md` against
`docs/quality/mock-data.md`. Local-only phase: no GCP access, no Terraform,
no Cloud SQL (the instance stays STOPPED throughout). Prerequisites (az CLI,
ADO sample org/project, backlog authoring, export) are codified in
Runbook 08.

Status: COMPLETE including phase-completion review (opened 2026-09-07;
increments 0–4 done 2026-09-08; completion review 2026-09-09 session 16 —
verdict Ready to close Phase 3, 3 Minor doc-drift findings fixed).

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
| 3 | Expected-file authoring | DONE (2026-09-08) |
| 4 | Loader harness + validation tests (test-first), Make target | DONE (2026-09-08) |

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
- [x] Increment 3 — expected files (2026-09-08, session 15, owner-approved
      shape + four decisions): expected contracts transcribed from the
      manual plans using schemas.md vocabulary. Owner-approved decisions:
      (1) `story_id` assigned `story-01`…`story-42` template-major
      (t1/clean=01 … t6/hidden-conflict=42), backfilled into all 42 story
      envelopes (additive field; recorded as a D9 amendment);
      (2) `expected_findings` are semantic stubs (`key`, `min_severity`,
      `topic`, `appears_in_version`, `resolved_at_turn`) — runtime finding
      IDs are reviewer-assigned and not pinned; deterministic asserts cover
      ID patterns/prefixes + severity ceilings, stub presence is
      judge-matched; (3) `expected_turns` includes turn 1 (opening
      facilitator turn) — one entry per dialogue turn; (4) conflicting
      closing = variant 1 (2-turn conversational finalize, no delegation).
      First authored as 42 per-template files, then COLLAPSED (same session,
      owner decision) to **7 scenario-canonical files**
      `dataset/expected/<scenario>.json` — the loader (increment 4) expands
      each to the 6 per-template test cases, deriving per-case
      case_id/story_id/template from the story envelopes; format invariance
      is now enforced structurally (D9 amendment 2). The per-template
      copies were moved to `trash/expected-per-template/` (never committed).
      Shape: deterministic fields (delegation invoke/reuse_previous/
      open_issues_empty, outcome, state_after, produced_artifact type+version,
      po_script exactly-one-of, expected_final incl. facilitator_turn_count)
      + semantic fields (`semantic_notes`, finding/conflict stubs).
      `facilitator_turn_count` follows the schemas.md rule that PO acceptance
      does not invoke the facilitator (clean=1, business/engineering-weak=2,
      partial-resolution=3, unresolvable=10). Unresolvable: turns 2–9 have
      routing/artifact versions deliberately unpinned (facilitator may
      delegate or continue); deterministic invariants are outcome=continue,
      open_issues never empty, park at facilitator turn 10, no reports.
      Post-authoring checks (run on the 42-file form, results identical by
      construction after the collapse): 42 cases, po_script exactly-one-of,
      turn numbering contiguous from 1, state matches outcome, reports only
      on finalize turns — all PASS. export_ado.py does not yet emit
      `story_id` on re-export — fold into increment 4.
- [x] Increment 4 — loader harness + REST export (2026-09-08, session 15,
      test-first): `dataset/loader/` uv package (`dataset-loader`) with
      strict models `StoryEnvelope` (envelope + minimal work-item field
      presence) and `ExpectedCase` (the full expected-file contract,
      vocabulary reused from `shared/review_schemas`: TurnOutcome,
      SessionState, ArtifactType, Format, StoryId) + loaders and the
      scenario→case expansion (42 cases) with invariants (unique sequential
      story-01…42, full 6×7 matrix, 1:1 scenario pairing, case-id/component
      match). 23 behavior tests (positive on the real dataset + negative
      fixtures) — written first, confirmed red, then implemented.
      `make dataset-test` added (mirrors `review-schemas-test`; both green:
      23 + 147). Data fix found by the tests: unresolvable conflict key
      `C-r1` violated the schemas.md `C-n` pattern — renamed to `C-1`
      (kind "recurring", deterministically_pinned false).
      `export_ado.py` now emits `story_id` (deterministic template-major
      numbering, loud abort on unregistered scenarios) and fetches via
      **REST with `$ADO_PAT` when set** (az CLI fallback otherwise) —
      WIQL via POST `_apis/wit/wiql`, items via GET `workitems/{id}?
      $expand=all` (the verified full-fidelity shape). Gotchas: `_rest`
      must join query params with `&` when the path already carries `?`
      (HTTP 400 'all?api-version' not valid for WorkItemExpand); context
      items carry no story_id. Re-export run via REST: all 45 files
      **content-identical** to the az export (programmatic semantic diff:
      only key order + exported_at differ), identifier check clean, loader
      green against the re-export. uv gotcha: `--with-editable
      shared/review_schemas` installs dist-info only (no .pth) from
      outside its directory — use `--with <path>` (regular build) instead.
      PAT lifecycle: `rest-verify` PAT retained for future re-exports;
      owner may revoke/rotate (export falls back to az CLI without it).
- [x] Independent read-only review of increment 4 (session 15, subagent,
      read-only): verdict **Ready to proceed** — no Critical/Important
      findings, 8 Minor (env guards in export_ado main, URLError catch,
      clearer story_id_for index + abort messages, po_accepted-requires-
      finalized validator, completed-reports == requested_formats
      cross-check, plain loop in expand_cases, narrowed pytest.raises,
      top-level test imports + 5 additional negative tests). All 8 fixed
      in the same session; suites re-run green (28 dataset + 147 schemas).
- [x] **Phase-completion review** (session 16, independent read-only
      subagent, contract boundary like Phase 2's post-review): verdict
      **Ready to close Phase 3** — 0 Critical / 0 Important / 3 Minor, all
      fixed same session:
      1. `docs/quality/mock-data.md` + `evaluation-tests.md` still described
         per-case expected files — realigned to scenario-canonical contract
         (commit docs-only/atomic per the docs-freeze cherry-pick rule);
      2. `dataset/story-templates.md` matrix paragraph listed six scenarios
         — hidden-conflict added;
      3. `dataset/canonical-facts.md` provenance lacked T5 cross-reference —
         added (T5 ids live in t5-enabler-spec.md, ids 42–48).
      Reviewer re-verified: 42 story files + 3 context, story_id template-major
      sequence, sanitization clean across all 111 dataset files, expected
      files expand to 42 cases, loader strict + vocabulary-consistent with
      review_schemas; suites 28 + 147 green.
