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

### Increment 1 (part 1) — dual-source design + schema + preparation (local, no cost)

Owner decisions (session 19, D10 in local-decisions.md): story MCP gets a
**dual data source** — production path reads live Azure DevOps (PAT: reuse
`rest-verify` from `ado.env`; Secret Manager at increment 5), mock path
serves the frozen dataset from GCS (`make dataset-push`, bucket bootstrap at
increment 5; local tests use a directory location). Source selection =
deployment env `STORY_SOURCE` + orchestration-only per-call override
(option a; stateless server). `StoryId` widened to
`^(story-[0-9]{2}|ado-[0-9]{1,8})$`. Evaluation runs always use `mock`.
Design docs changed atomically and cherry-picked to `docs/initial-frozen`
(`37309db`→`5ab7380`, `336ea8e`→`7eb9cec`).

- `shared/review_schemas` **0.4.0**: `StorySource` + `source` field on
  `ListStoriesInput`/`GetStoryInput` + widened `StoryId` (test-first red:
  missing `source` attr / `ado-5` rejected).
- `mcp_servers/story/` uv package `story-mcp`: `flatten.py` (stdlib HTML
  flattener), `prepare.py` (ADO→`StoryDetail` per the owner-approved mapping
  table — presented and approved in chat; scenario/template never mapped),
  45 **golden snapshots** in `tests/golden/` (owner-reviewed once,
  `tests/generate_golden.py` regenerates).
- New Makefile target `mcp-story-test` (pattern of `dataset-test`, with
  `--with ../../dataset/loader` for the envelope models).

```
make mcp-story-test        # red first (ModuleNotFoundError story_mcp[.prepare]), then 21 passed
make review-schemas-test   # 154 passed (152 + 2 new source/id tests)
make dataset-test          # 36 passed (untouched)
```

Gotchas learned:

- Identifier check with an unset variable matches everything (empty regex
  alternation) — always source BOTH `home.env` and `ado.env` before `rg
  -l "$PROJECT_ID|$ADO_ORG|..."`; post-commit re-check was clean.
- Context envelopes (`dataset/stories/context/`) are full envelopes with a
  `work_item` key, not bare work items — `ContextIndex.from_items` accepts
  both shapes.
- `StoryComment.created_at` (AwareDatetime, strict) needs a parsed
  `datetime` — `fromisoformat` with `Z`→`+00:00`, not a raw string.
- Schema-change review deferred to the full increment-1 review (server +
  contract tests still to come).
- (Carried from increment 0) `tests/test_package_install.py` pins both the
  package version and the exact `__all__` list — a version bump or new
  export must update that test in the same change.
- (Carried from increment 0, now superseded by D10) `StoryId` pattern was
  `story-NN` two digits only; now `story-[0-9]{2}|ado-[0-9]{1,8}`.

### Increment 1 (part 1b) — ADO wire models extracted to `shared/ado_wire` (local, no cost)

D9 amendment 6. Split extraction (implementation subagent, owner-reviewed
diff): `WorkItem`/`WorkItemComment` moved verbatim from
`dataset_loader.envelope` to new shared package `shared/ado_wire` (pydantic
only); `StoryEnvelope` + dataset aliases stay in the loader, which
re-exports the moved models. Existing test files byte-identical; new tests
in `shared/ado_wire/tests/` (7). Motivation: the story server (and future
live `azure` source) imports wire shapes without a loader dependency for
them; Docker context shrinks accordingly (still needs `dataset/loader` for
`StoryEnvelope` on the mock path).

```
make ado-wire-test       # 7 passed (red first: ModuleNotFoundError ado_wire)
make dataset-test        # 36 passed (untouched)
make mcp-story-test      # 21 passed
make review-schemas-test # 154 passed (untouched)
```

Gotchas learned:

- A stale uv-cached `dataset-loader` wheel served an old `envelope.py`
  during the refactor — `uv cache clean` resolves it (hit once during
  implementation, verified after).
- Subagent-assessed first (cheap-model read-only pass) that the move could
  keep all three existing test dirs byte-identical — held true; only
  packaging/imports changed.
