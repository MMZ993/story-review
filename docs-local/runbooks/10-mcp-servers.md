# Runbook 10 — MCP servers (Phase 4)

Codifies the Phase 4 work: three MCP servers (story, artifact, report),
local compose stack, and Cloud Run deploys, per
`docs-local/plans/phase-4-mcp-servers.md` and `docs/design/mcp-servers.md`.
Local increments are no-cost; the deploy increment (Cloud Run + GCS smoke)
is owner-approved before execution.

Status: IN PROGRESS (opened 2026-09-09).

## Increment 0 — shared-schema catch-up + decisions (local, no cost)

Executed 2026-09-09 (session 17). No environment commands — code + tests only:

```
make review-schemas-test   # red first (ImportError: ContextStory), then green
make dataset-test          # untouched loader suite, still green
```

Owner decisions (recorded as D9 amendment 4 in local-decisions.md):
`StoryComment.author` kept; preparation at server startup (HTML flattening +
field mapping in memory, golden-snapshot pinned); PDF library deferred to
increment 3.

Changes (test-first):

- `shared/review_schemas/review_schemas/review.py`: `StoryComment`
  (`author`, `text`, `created_at`) and `ContextStory` (`relation`
  `related|depends`, own `acceptance_criteria` cap 100 + `comments` cap 50)
  added; `StoryDetail` gains `comments` (cap 50, default empty) and
  `context_stories` (cap 5, default empty) — exactly
  `docs/design/schemas.md`.
- `review_schemas/__init__.py`: both models re-exported; exports test list
  updated.
- `pyproject.toml`: version 0.1.0 → 0.2.0 (package-install test updated to
  match).

Evidence: `make review-schemas-test` **151 passed** (147 + 4 new behavior
tests plus extended default assertions in the existing summary/detail test:
valid nested payload, strict-field rejection, relation literal, cap 50/5
overflow); `make dataset-test` **36 passed**.

### Increment 1 correction — runtime story contract (local, no cost)

Owner-approved 2026-09-09. Before story-server preparation began, the owner
identified `StorySummary.quality_class` as an evaluation-data leak: real Azure
DevOps stories do not know their expected review result. The authoritative
schema, shared implementation, and all public API/MCP consumers now omit it;
`dataset` retains its `scenario` only for test evaluation. The new behavior
contract rejects a public story payload carrying `quality_class`.

```
make review-schemas-test  # focused test red first, then 152 passed green
```

Gotchas learned:

- `tests/test_package_install.py` pins both the package version and the
  exact `__all__` list — a version bump or new export must update that test
  in the same change (failures are loud, not silent).
- `StoryId` pattern is `story-NN` (two digits) — dataset story ids 01–45
  fit; revisit if the dataset ever exceeds 99.
