# Phase 2 — Shared schemas package plan

## Objective

Implement `shared/review_schemas` as the single, installable Pydantic v2 package
specified by `docs/design/schemas.md`. It is a local-only contract increment: no
Cloud SQL resume, Terraform, container build, or GCP deployment is needed.

The package is the boundary contract for later dataset, MCP, agent, orchestration,
and TUI work. This phase implements the frozen specification exactly; it does not
redesign fields, loosen validation, or add runtime services.

## Preconditions

- Phase 1 is complete: the end-to-end connectivity trace passed under the documented
  D8 ingress fallback, spike resources were removed, and Terraform had no drift.
- Cloud SQL remains paused. Phase 2 must not run `make db-resume`.
- `docs/design/schemas.md` remains the authoritative contract. Any discovered
  ambiguity stops implementation until it is resolved in the design or recorded as a
  local decision.

## Deliverables

```text
shared/review_schemas/
├── pyproject.toml                 # package metadata, semantic version 0.1.0
├── requirements.in                # runtime dependency inputs
├── requirements.lock              # uv-compiled runtime lock
├── review_schemas/
│   ├── __init__.py                # deliberate public re-exports
│   ├── base.py                    # StrictModel, aliases, literals
│   ├── errors.py                  # ErrorBody, ErrorEnvelope, ToolError
│   ├── review.py                  # story/review models
│   ├── synthesis.py               # conflicts, artifact references, synthesis
│   ├── facilitator.py             # delegation/resolution/finalization/conversation
│   ├── judge.py                   # judge dimension/issue/result models
│   ├── api.py                     # HTTP request, response, health models
│   ├── records.py                 # durable Cloud SQL record models
│   └── mcp.py                     # MCP input/output models
└── tests/
    ├── requirements.in
    ├── requirements.lock
    ├── conftest.py                # fixed UUID/timestamp/reference fixtures only
    ├── test_base_and_errors.py
    ├── test_review_models.py
    ├── test_api_models.py
    ├── test_records.py
    ├── test_mcp_models.py
    └── test_package_install.py
```

The package modules remain implementation details; `__init__.py` exposes the stable
consumer API. `ArtifactRecord` stays explicitly internal despite being importable by
trusted persistence code.

The domain group is split across `review.py`, `synthesis.py`, `facilitator.py`, and
`judge.py` to respect the < ~300-line module guideline (the specification's domain
section alone is roughly 450 lines of models). Internal imports stay one-directional
(`review` → `synthesis` → `facilitator`); only `__init__.py` re-exports them, so
consumers see one flat public API regardless of the internal split.
`test_review_models.py` spans those four modules as one domain group.

Evidence goes into a new Phase 2 runbook entry,
`docs-local/runbooks/07-shared-schemas.md`, created when implementation starts.

## Implementation increments

### 1. Package skeleton and strict primitives

1. Create package metadata with Python and Pydantic v2 constraints already used by
   the source, initial semantic version `0.1.0`, and a conventional package layout.
2. Add `StrictModel`, all constrained aliases, ID/literal types, and UTC timestamp
   alias exactly as named in the schema specification.
3. Compile the runtime lock with `uv pip compile`; compile a separate test lock that
   installs the local package by path plus pytest.
4. Add a Make target, `review-schemas-test`, using only the test lock.
5. First write and run failing tests for unknown-field rejection, Python-mode strict
   rejection of coerced values, JSON-mode UUID/timestamp decoding, identifier
   patterns, text bounds/stripping, and timezone-aware datetimes. Then implement
   the smallest code to pass them.

### 2. Error and domain model groups

Implement in specification order, with tests written before each group:

1. Error taxonomy and retry-hint invariant: `ErrorBody`, `ErrorEnvelope`, and
   `ToolError`.
2. Story/review/synthesis/delegation/finalization/conversation/judge models,
   including finding-prefix, artifact reference, paired-input, delegation,
   final-state, and judge pass-threshold validators.
3. Test both valid boundary examples and one observable invalid combination for
   every cross-field invariant. Use fixed valid nested fixtures rather than testing
   Pydantic internals or validator implementation details.

### 3. API and durable-record groups

1. Implement list/create/turn/finalization/report/health API models and canonical
   operation-result union.
2. Implement durable story-run, session, lease, turn, and agent-run records.
3. Cover header/body-adjacent models indirectly through their model contracts:
   unique requested formats, exact-one turn action, outcome/state alignment,
   report/reference compatibility, completion requirements, turn state, and agent
   attempt limits.

FastAPI routes and SQL mappings are explicitly deferred to Phase 6; these are
validation contracts only.

### 4. MCP contract group and consumer proof

1. Implement all MCP inputs/outputs and their lineage/type/perspective validators.
2. Test save/get content exact-type checks, list filter compatibility, and report
   reference/format rules.
3. Add an install/import test in a clean temporary virtual environment or equivalent
   declared `uv` path-install invocation. It must import the public API from the
   installed package, not by relying on the repository working directory.
4. Verify the public export list deliberately includes every model/type required by
   later consumers and excludes no model that the schema declares shared.

## Verification gates

For each increment:

```bash
make review-schemas-test
```

At phase completion also run:

```bash
uv pip compile shared/review_schemas/requirements.in \
  -o shared/review_schemas/requirements.lock
uv pip compile shared/review_schemas/tests/requirements.in \
  -o shared/review_schemas/tests/requirements.lock
make review-schemas-test
```

Record the exact passing count and package-install command/output in the Phase 2
runbook evidence. Inspect the final diff against `docs/design/schemas.md` to confirm
all named aliases, literals, models, defaults, bounds, unions, and validators are
represented. Request an independent read-only review before accepting the phase,
because this is a shared schema and security/contract boundary.

## Exit criteria

- Every model and validator in `docs/design/schemas.md` is implemented with the same
  field names, defaults, constraints, and observable validation behavior.
- Deterministic unit tests pass, including valid and invalid cross-field cases.
- `shared/review_schemas` installs by local path from its locked requirements and its
  public API imports successfully outside the source working directory.
- The package version is `0.1.0`; later contract changes require a semantic version
  bump and consumer-lock updates.
- Phase 2 evidence is recorded in a new runbook entry; Cloud SQL remains stopped.

## Out of scope

- Dataset files and expected outcomes (Phase 3).
- MCP servers, Compose, Docker images, or Cloud Run deployment (Phase 4).
- Agents, prompts, FastAPI, migrations, and TUI work (Phases 5–7).
- Any infrastructure or IAM change.

## Risks and controls

| Risk | Control |
|---|---|
| A model silently diverges from the frozen design | Implement from the specification in groups and complete a named-model diff review. |
| Pydantic strict-mode assumptions differ between Python and JSON input | Test both `model_validate` and `model_validate_json` at the boundary. |
| A broad export or circular import destabilizes consumers | Keep imports one-directional (`base` → domain groups; public re-exports only in `__init__`) and test installed imports. |
| Schema scope expands into application work | Enforce the out-of-scope list and defer integration behavior to its scheduled phase. |

## References

- `docs/design/schemas.md` — authoritative field-level contract.
- `docs/operations/repository-layout.md` — package/versioning/staging rules.
- `docs-local/development-plan.md` — Phase 2 scope and exit criterion.
- `.agents/development-rules.md` — strict Pydantic, documentation-first, test-first,
  and independent-review requirements.
