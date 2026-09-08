# dataset-loader

Trivial load/validate harness for the Phase 3 mock dataset — Runbook 09
increment 4 (`docs-local/plans/phase-3-mock-dataset.md`). No server, no
query engine; it loads and validates only.

- `dataset_loader/envelope.py` — strict `StoryEnvelope` model for the
  D9 export format (case id, story id, template, scenario, verbatim
  `work_item`; minimal work-item field presence checks).
- `dataset_loader/expected.py` — strict `ExpectedCase` model for the
  scenario-canonical expected-file contract (deterministic fields:
  delegation/outcome/state/artifacts/po_script/final; semantic fields:
  finding + conflict stubs).
- `dataset_loader/dataset.py` — loaders + the scenario→case expansion
  (42 test cases from 42 stories × 7 expected contracts) and the dataset
  invariants (unique sequential story ids, full 6×7 matrix, 1:1 scenario
  pairing).

Vocabulary (TurnOutcome, SessionState, ArtifactType, Format, StoryId) is
reused from the Phase 2 `shared/review_schemas` package. Run:

```bash
make dataset-test
```

Expected files are excluded from every runtime image
(`docs/operations/repository-layout.md`) — this package is test tooling,
not a runtime dependency.
