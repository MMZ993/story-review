# Runbook 07 — Phase 2: shared schemas package (`shared/review_schemas`)

Implements `docs-local/plans/phase-2-shared-schemas.md` against the frozen contract
`docs/design/schemas.md`. Local-only phase: no GCP access, no Terraform, no Cloud SQL
(the instance stays STOPPED throughout).

Status: IN PROGRESS 2026-09-06 (session 9: increment 1 — package skeleton and strict
primitives).

## Scope

- `shared/review_schemas` — versioned Pydantic v2 package (semver `0.1.0`), public
  API re-exported from `review_schemas/__init__.py`; module layout per the Phase 2
  plan.
- Verification per increment: `make review-schemas-test` (deterministic unit tests
  via the compiled test lock only).
- Phase-completion gate: recompile both locks, re-run tests, named-model diff review
  against `docs/design/schemas.md`, independent read-only review.

## Increments

| # | Scope | Status |
|---|---|---|
| 1 | Package skeleton, strict primitives (`base.py`), locks, Make target | DONE (2026-09-06) |
| 2 | Errors + story/review/synthesis/facilitator/judge domain group | DONE (2026-09-06) |
| 3 | HTTP API + durable Cloud SQL record models | DONE (2026-09-06) |
| 4 | MCP tool models, consumer install/import proof, diff review, independent review | TODO |

Increment 4 must include a mechanical export-list test in
`test_package_install.py`: assert `__all__` equals exactly the set of shared
names declared in `docs/design/schemas.md` (no missing, no extras) and that
`ArtifactRecord` is **not** re-exported — so the internal/public boundary is
CI-enforced, not convention (decision from session 9: keep `ArtifactRecord`
inside the shared package per the frozen spec; moving it out would be a
future design change).

## Increment 1 — package skeleton and strict primitives

Commands (all local, no side effects outside the repository). Note: the locks
must be compiled from inside their own directories, because uv resolves
relative paths in `requirements.in` files against the invocation cwd — see
gotchas.

```bash
# Runtime lock (Python + Pydantic v2 constraints as used by the source)
cd shared/review_schemas
uv pip compile requirements.in -o requirements.lock

# Test lock (pytest only; the package itself is installed by path in the
# Make target via --with-editable .)
cd tests
uv pip compile requirements.in -o requirements.lock

# Run the deterministic suite
cd ../../..
make review-schemas-test
```

Test-first order: `tests/test_base_and_errors.py` (base part) was written and run
**before** `review_schemas/base.py` existed, confirming failures for the right
reason (ImportError), then implemented.

### Evidence

- Test-first confirmed: suite run before `review_schemas/base.py` existed
  failed with `ImportError` on `review_schemas.base` (right reason).
- After implementing `base.py`: **26 passed** (`26 passed in 0.06s`), zero
  warnings/skips, via `make review-schemas-test`.
- Phase-gate re-run after recompiling both locks: still **26 passed**;
  `git diff --check` clean.
- Locked versions: pydantic 2.13.5 (pydantic-core 2.46.5, annotated-types
  0.8.0); test lock pytest 9.1.1. Python 3.13.3 (uv-managed) — package
  `requires-python = ">=3.12"`.
- Coverage of this increment: unknown-field rejection (Python + JSON mode),
  strict-mode rejection of UUID/timestamp coercion in Python mode, JSON-mode
  UUID/timestamp string decoding (incl. malformed UUID rejection), ID pattern
  and length checks for all five prefixed ID types, Text/ShortText stripping
  and exact bounds (20,000 / 500), Sha256 64-lowercase-hex, https-only URL,
  aware-datetime requirement (naive rejected, non-UTC aware accepted),
  Format literal acceptance/rejection.

### Gotchas

- **uv resolves relative paths in requirements files against the invocation
  cwd, not the file's directory**: `-e ..` in `tests/requirements.in` pointed
  at `shared/` when compiled from the package root. Fix: compile from inside
  `tests/`, and keep the test lock pytest-only.
- **`uv run --with-requirements <lock>` does not install editable/path
  entries from the lock** (`-e ..` was silently not importable). Fix: the
  Make target installs the package with `--with-editable .` alongside the
  lock; the requirements.in comment documents this.
- **hatchling fails the build if `readme = "README.md"` is declared but the
  file is absent** — a minimal README is part of the skeleton.
- The prefixed IDs (`run-`, `sess-`, `art-`, `arun-`) embed the *hyphenated*
  UUID string (36 chars → total length 40/41), not 32 plain hex chars; the
  fixture UUID string must keep the hyphens.

## Increment 2 — error and domain model groups

Implemented `errors.py`, `review.py`, `synthesis.py`, `facilitator.py`,
`judge.py` verbatim from the corresponding `docs/design/schemas.md` sections;
grew the public `__init__` re-exports (39 names; `ArtifactRecord` deliberately
internal). Tests written first (`test_base_and_errors.py` TestErrors + new
`test_review_models.py`), confirmed red on ImportError, then green.

### Evidence

- `make review-schemas-test`: **62 passed** (26 increment-1 + 5 errors + 31
  domain), zero warnings/skips, after implementation and again after the
  `__init__` export change; `git diff --check` clean.
- Validator coverage (valid boundary + observable invalid per invariant):
  retry-hint invariant and bounds; finding-prefix/perspective match;
  ArtifactReference perspective↔type and content-type↔type maps (incl.
  non-review types rejecting any perspective); ArtifactRecord gs:// URI;
  SynthesisReport paired inputs (missing key, wrong ref type, cross-run);
  DelegationDecision reuse/extra-context combination; FacilitatorTurnOutput
  resolutions-on-reuse-only-turn; FinalizedReview synthesis-reference
  run/type match and open-issues-requires-acceptance; JudgeResult dimension
  uniqueness, 0–4 bounds, pass threshold (min ≥ 3, avg ≥ 3.5, no blocker).

### Gotchas

- Pydantic field constraints fire **before** model validators, so some
  invalid inputs are rejected with the constraint error, not the validator's
  message (e.g. a 1-key `inputs` dict fails `too_short` before the paired-input
  validator; a JudgeResult score of 5 fails the 0–4 bound before the pass
  rule). Tests assert the observable rejection, not the message.
- Constructing an alternate run ID by reversing the fixture UUID string breaks
  the 8-4-4-4-12 hex groups (first group becomes 12 chars); use a second fixed
  UUID-shaped fixture instead (`OTHER_RUN_ID` in the domain tests).

## Increment 3 — HTTP API and durable-record groups

Implemented `api.py` and `records.py` verbatim from the corresponding
`docs/design/schemas.md` sections; extended the public `__init__` exports
(now 64 names incl. `CanonicalOperationResult` and the five record models;
`ArtifactRecord` still internal). Tests written first (`test_api_models.py`,
`test_records.py`), confirmed red on ImportError, then green. The shared
`artifact_reference` fixture helper moved from `test_review_models.py` to
`conftest.py` (used by three test files).

### Evidence

- `make review-schemas-test`: **99 passed** (62 previous + 37 new), zero
  warnings/skips, after implementation and again after the `__init__` export
  change; `git diff --check` clean.
- Contract coverage: unique requested formats (request/summary/record);
  exact-one turn action (TurnRequest, TurnView, TurnRecord, incl. turn-1
  exemption); outcome↔state alignment and report-on-finalize-only + unique
  formats (TurnResponse, CanonicalTurnResult); report-format↔reference match
  (ReportDownload); issues-mirror-delegation (Create/TurnResponse); opening
  no-delegate rule; SessionDetail completion (all requested formats, none
  before completed); SessionRecord completion contract (final review of this
  run + exact report-format set); TurnRecord succeeded requires outcome +
  completion time; AgentRunRecord facilitator-only attempt limits (≤2
  transport attempts, corrective re-prompts facilitator-only, finished states
  require finished_at).

### Gotchas

- `CreateSessionResponse.state` (`Literal["active"]`) and
  `opening_turn_number` (`Literal[1]`) are required fields without defaults —
  test fixtures must pass them explicitly; the validator tests then hit the
  intended validator instead of `Field required`.
