# Dataset — mock story review matrix

Ground truth for the story-review system's evaluation runs
(`docs/quality/mock-data.md`, plan: `docs-local/plans/phase-3-mock-dataset.md`).
Local-only: no GCP, no runtime concerns here.

## Provenance and how to reproduce

Source of truth is the free Azure DevOps org/project `$ADO_ORG` /
`$ADO_PROJECT` (values in gitignored `infra/envs/ado.env`; see Runbook 08).
The matrix: 7 scenarios × 6 templates (T1–T6) = 42 stories, ADO ids 5–55,
plus epic id 2 and features ids 3–4 as hierarchy context.

Reproduce the export:

```bash
set -a; source infra/envs/ado.env; set +a
python3 dataset/tools/export_ado.py
```

## Layout

```text
dataset/
├── tools/export_ado.py      # ADO → dataset/stories/ export (below)
├── canonical-facts.md       # per-scenario facts; renderer input for T2–T4, T6
├── t5-enabler-spec.md       # authoring input for the T5 enabler column
├── story-templates.md       # template/matrix design (T1–T6)
├── drafts/                  # authoring-time drafts + self-checks (not runtime data)
├── manual-plans/            # per-scenario manual test plans (format invariance)
├── stories/                 # exported story JSON (this is the serving input)
│   ├── context/             # epic + features — hierarchy context, not test cases
│   └── t1..t6/<scenario>.json
└── expected/                # expected-file contracts (Runbook 09 increment 3)
```

## Conventions (D9 + session-14 amendment, `docs-local/local-decisions.md`)

- **Test case = one story in one template**: case id `<template>/<scenario>`
  (e.g. `t3/conflicting`). A stress duplicate of the same content becomes
  `<scenario>-2.json` — a separate test case by construction.
- **Format invariance**: every template variant of a scenario must pass the
  same scenario manual plan (`manual-plans/<scenario>.md`) unchanged —
  same steps, same expected arc.
- Each story file = envelope + verbatim ADO work-item JSON under `work_item`:

```json
{
  "schema_version": 1,
  "case_id": "t3/conflicting",
  "template": "t3",
  "scenario": "conflicting",
  "ado_source_id": 31,
  "exported_at": "2026-09-07T21:09:28+00:00",
  "work_item": { "...": "verbatim az boards work-item show --expand all output" }
}
```

- ADO ids are authoring-time references only (`ado_source_id` provenance);
  the stable dataset key is the case id.
- Export sanitization (identifier hygiene): `_links` keys dropped; URL
  strings rewritten to `$ADO_ORG` / `<project-id>` placeholders. Everything
  else verbatim, HTML fields included — fidelity/trimming is a separate
  later preparation step against these files, never a transform-on-export.
- Stories carry no Effort (review happens pre-estimation, in the backlog).

## License note

All story content is fictional, authored for this capstone project.
