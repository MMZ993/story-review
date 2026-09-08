# Dataset — mock story review matrix

Ground truth for the story-review system's evaluation runs
(`docs/quality/mock-data.md`, plan: `docs-local/plans/phase-3-mock-dataset.md`).
Local-only: no GCP, no runtime concerns here.

## Provenance and how to reproduce

Source of truth is the free Azure DevOps org/project `$ADO_ORG` /
`$ADO_PROJECT` (values in gitignored `infra/envs/ado.env`; see Runbook 08).
The matrix: 7 scenarios × 6 templates (T1–T6) = 42 stories, ADO ids 5–55,
plus 3 t1-only comment scenarios (D9 amendment 3): `comments-benign`
(ADO id 57, story-43), `comments-clarify-business` (58, story-44),
`comments-complete-engineering` (59, story-45) — authored per
`comments-stories-spec.md`; plus epic id 2 and features ids 3–4 as
hierarchy context.

Reproduce the export:

```bash
set -a; source infra/envs/ado.env; set +a
python3 dataset/tools/export_ado.py
```

## Layout

```text
dataset/
├── tools/export_ado.py      # ADO → dataset/stories/ export (below; REST
│                         #   via $ADO_PAT when set, az CLI fallback)
├── loader/                  # load/validate harness (Runbook 09 incr. 4;
│                         #   make dataset-test; test tooling, not runtime)
├── canonical-facts.md       # per-scenario facts; renderer input for T2–T4, T6
├── t5-enabler-spec.md       # authoring input for the T5 enabler column
├── story-templates.md       # template/matrix design (T1–T6)
├── drafts/                  # authoring-time drafts + self-checks (not runtime data)
├── manual-plans/            # per-scenario manual test plans (format invariance)
├── stories/                 # exported story JSON (this is the serving input)
│   ├── context/             # epic + features — hierarchy context, not test cases
│   └── t1..t6/<scenario>.json
└── expected/                # expected-file contracts (Runbook 09 increment 3)
    └── <scenario>.json        # 7 canonical scenario files — one per manual plan;
                               # the loader expands each to 6 per-template test
                               # cases (per-case story_id/case_id from the
                               # story envelopes)
```

## Conventions (D9 + session-14 amendment, `docs-local/local-decisions.md`)

- **Test case = one story in one template**: case id `<template>/<scenario>`
  (e.g. `t3/conflicting`). A stress duplicate of the same content becomes
  `<scenario>-2.json` — a separate test case by construction.
- **Expected files are scenario-canonical** (owner decision, session 15,
  collapsing the first per-template authoring): `dataset/expected/
  <scenario>.json` — 7 files, one per manual plan. Format invariance is
  enforced structurally: the loader expands each scenario file to the 6
  per-template test cases, deriving `case_id`/`story_id`/`template` from the
  story envelopes (D9 amendment 2). A future case needing template-specific
  expectations (e.g. a stress duplicate) gets its own expected file.
- Each story file = envelope + verbatim ADO work-item JSON under `work_item`:

```json
{
  "schema_version": 1,
  "case_id": "t3/conflicting",
  "story_id": "story-22",
  "template": "t3",
  "scenario": "conflicting",
  "ado_source_id": 31,
  "exported_at": "2026-09-07T21:09:28+00:00",
  "work_item": { "...": "verbatim az boards work-item show --expand all output" }
}
```

- ADO ids are authoring-time references only (`ado_source_id` provenance);
  the stable dataset key is the case id.
- Extension envelope fields (D9 amendment 3, both optional/default empty —
  additive; pre-extension files unaffected):
  - `comments`: verbatim sanitized ADO comments-API objects (non-empty
    `text`; cap 50). Semantic review input — comment content can resolve or
    create findings. The design-level `StoryComment`
    (author/text/created_at) mapping happens in the Phase 4 story MCP.
  - `linked_stories`: case-id references to other story files (max 5,
    unique, no self-reference, must resolve — enforced by the loader).
    Linked stories are context/reference material for the main story's
    review, never reviewed themselves.
- Export sanitization (identifier hygiene): `_links` keys dropped; URL
  strings rewritten to `$ADO_ORG` / `<project-id>` placeholders. Everything
  else verbatim, HTML fields included — fidelity/trimming is a separate
  later preparation step against these files, never a transform-on-export.
- Stories carry no Effort (review happens pre-estimation, in the backlog).

## License note

All story content is fictional, authored for this capstone project.
