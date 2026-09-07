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
| 2 | Errors + story/review/synthesis/facilitator/judge domain group | TODO |
| 3 | HTTP API + durable Cloud SQL record models | TODO |
| 4 | MCP tool models, consumer install/import proof, diff review, independent review | TODO |

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
