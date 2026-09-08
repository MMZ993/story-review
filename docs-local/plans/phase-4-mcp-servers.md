# Phase 4 — MCP servers + local compose plan

## Objective

Build the three purpose-scoped MCP servers (story, artifact, report) from
`docs/design/mcp-servers.md`, each with a Dockerfile, a Cloud Run deploy
manifest, and contract tests; plus the local compose stack
(`deploy/docker-compose.yml`, `local` profile) they run in. Story serving is
backed by the frozen mock dataset (45 stories incl. comments); expected files
never enter a runtime image.

Per development-plan.md exit criteria: contract tests pass against the local
compose services; each server deploys to Cloud Run via a Makefile target and
answers a smoke call.

Cost: Cloud Run (min instances 0) + GCS for smoke tests — minimal. Cloud SQL
stays STOPPED for all local increments; it is resumed only if a deploy/smoke
increment needs it (none is expected to — the artifact server uses GCS, not
SQL).

## Preconditions

- Phase 3 complete and closed (Runbook 09 COMPLETE, completion review
  Ready-to-close); dataset extensions session done (comments envelope
  structure codified, D9 amendment 3).
- `docs/design/schemas.md` and `mcp-servers.md` already carry the
  comments/context-stories contract (commits `52534ef`, `9b430ce`,
  `5e35128`).
- Spike evidence available: `spikes/connectivity/spike_mcp/` (ID-token
  middleware, stateless Streamable-HTTP app wiring, Cloud Run MCP deploy
  pattern — Runbook 06). Spike source is a reference, not a dependency;
  Phase 4 code is written fresh under `mcp_servers/`.

## Open decisions to settle in increment 0 (owner)

1. **`StoryComment.author`** — spike note says the story MCP will likely drop
   comment authors entirely (single anonymized persona adds nothing). If
   dropped, `docs/design/schemas.md` changes (owner-approved, separate atomic
   docs commit, cherry-picked to `docs/initial-frozen`); if kept, the
   preparation step maps the anonymized persona.
2. **Preparation step mechanics (D9 fidelity/trimming)** — how the verbatim
   ADO envelope becomes the design `StoryDetail`:
   - HTML fields (`System.Description`, `AcceptanceCriteria`) → plain text:
     flatten at MCP build/startup into the design schema. Working assumption:
     flatten (tags stripped, entity-decoded, block tags → newlines); the
     design's `Text` fields are plain text.
   - Mapping table: `System.Title`→`title`, `System.State`→`status`,
     area/tag-based `quality_class`, parent Feature/Epic → `epic_context`,
     roadmap context from the epic envelope in `dataset/stories/context/`.
   - Where preparation runs: image build time (baked `StoryDetail` JSON) vs
     server startup (in-memory). Working assumption: startup, reading
     `/app/dataset/stories/` — keeps images dataset-agnostic and reuses the
     loader's envelope models.
   - `context_stories`: `relation` lives in ADO relations (`Hierarchy-Forward`
     / `System.LinkTypes.Related` etc.); with extension-2 mock data deferred,
     only the mapping for `linked_stories` refs is codified; the runtime path
     exercises it with empty lists until data exists.
3. **PDF rendering library** for the report server (design says MD + PDF,
   deterministic, no LLM). Working assumption: markdown → HTML → PDF via a
   pinned pure-Python stack in `requirements.lock` (e.g. `markdown-it-py` +
   `weasyprint` or `fpdf2`), decided at increment 3 against image size and
   determinism.

Recorded outcomes go to `docs-local/local-decisions.md` (new D-number or D9
amendment 4, as the owner prefers).

## Deliverables

- `shared/review_schemas`: `StoryComment` + `ContextStory` models on
  `StoryDetail` (test-first), package version bump — code catching up to
  schemas.md.
- `mcp_servers/story/` — server, preparation step, Dockerfile (copies
  `dataset/stories/` only, never `dataset/expected/` or dataset root),
  requirements.in/lock, tests.
- `mcp_servers/artifact/` — GCS-backed artifact store, Dockerfile, tests.
- `mcp_servers/report/` — deterministic MD/PDF renderer, Dockerfile, tests.
- `deploy/docker-compose.yml` (`local` profile) + `deploy/env/.env.example`;
  `deploy/compose/` substitutes as needed (fake-gcs-server; no agents yet —
  `local-agents` profile is Phase 5).
- `deploy/cloud-run/{story,artifact,report}/{deploy.sh,.env.example}`.
- Makefile: real `compose-up`/`compose-down`, `mcp-*-test`, and
  `mcp-*-deploy` + `mcp-*-smoke` targets.
- Runbook 10 (`docs-local/runbooks/10-mcp-servers.md`) — codified commands
  and evidence per increment.

## Implementation increments

### 0. Shared-schema update + open decisions (local, no cost)

Test-first: add `StoryComment`, `ContextStory` to
`shared/review_schemas/review.py` exactly per schemas.md (strict, caps 50/5,
`relation` literal `related|depends`); negative tests (unknown fields, cap
overflow, bad relation). Bump package version. Settle the three open
decisions above with the owner; record them. `make review-schemas-test`
green (147 → more).

### 1. Story MCP server (local)

- Preparation module: envelope (loader's `StoryEnvelope`) → `StoryDetail`,
  per the increment-0 mapping table; unit tests against all 45 real story
  files (byte-stable output asserted per file — a golden snapshot committed
  once, owner-reviewed).
- Server: FastMCP/`mcp` SDK Streamable HTTP, stateless; tools
  `list_stories` / `get_story` with the shared input/output models;
  `list_stories` excludes context-only stories; every failure returns
  `ToolError(ErrorBody)` with the stable codes from mcp-servers.md.
- Ingress: ID-token middleware pattern from the spike; **disabled only in
  the local profile** (compose env), fail-closed in production shape.
- Contract tests: tool-level against the ASGI app (TestClient + MCP client
  SDK), incl. unknown-field rejection, error taxonomy, caller allowlist
  (orchestration/facilitator principals; story server has no
  orchestration-only tools but the principal plumbing is proven here).
- Dockerfile per repository-layout.md (root context, copies
  `mcp_servers/story`, `shared/review_schemas`, `dataset/stories/` only).

### 2. Artifact MCP server (local, fake GCS)

- `GcsArtifactService` against the storage library with an injectable
  endpoint (fake-gcs-server locally, real GCS in Cloud Run) — same code path.
- Tools `save_artifact` / `get_artifact` / `list_artifacts` with the
  lineage-scoping, idempotency (`(story_run_id, type, idempotency_key)` +
  `IDEMPOTENCY_KEY_REUSED` on content mismatch), immutability, and
  `(type, perspective, version)` ordering rules from mcp-servers.md and
  `shared/review_schemas/mcp.py` validators.
- Contract tests: cross-run read rejected, retry-idempotency, pagination,
  `is_latest` derivation, save tool forbidden to facilitator principal.
- Dockerfile: no dataset at all.

### 3. Report MCP server (local, fake GCS)

- `render_report`: reads the referenced `finalized-review` artifact (same
  run only), renders MD and PDF deterministically; idempotent per
  `(story_run_id, format)` with conflict on a different finalized-review
  reference; saves `report-<format>` artifact via the storage service.
- Contract tests against fake GCS incl. determinism (two renders →
  byte-identical MD), wrong-reference and cross-run rejections.
- Dockerfile: renderer dependency pinned in `requirements.lock`; verify
  image size stays reasonable (PDF stacks can be heavy — decide library
  here).

### 4. Local compose + cross-service contract tests

- `deploy/docker-compose.yml` `local` profile: three MCP services +
  fake-gcs-server with pre-created buckets; SA ingress checks off via env;
  story image mounts/copies `dataset/stories/`.
- Real Makefile `compose-up`/`compose-down`.
- Contract tests run against the **running compose services** over HTTP
  (direct `mcp` SDK client, as orchestration will): full tool matrix, error
  taxonomy over the wire, idempotency across a container restart.
- This is the Phase 4 exit gate #1.

### 5. Cloud Run deploys + smoke (write actions — owner-approved, Runbook 10)

- `deploy/cloud-run/<service>/deploy.sh` + `.env.example` per the spike's
  proven pattern; service-account-only ingress; GCS buckets for artifacts
  (bootstrap additions if needed — Terraform, plan-before-apply).
- Makefile `mcp-story-deploy` / `mcp-artifact-deploy` / `mcp-report-deploy`
  and matching smoke targets (authenticated `list_stories`, artifact
  save/get roundtrip, MD render) — smoke from local machine with ADC +
  caller SA identity per connectivity-identity.md.
- Pipelines (`.yml`) are **out of scope** (D3: written at promotion).
- This is exit gate #2. Cloud Run min instances 0; cost near-zero.

## Verification gates

- Each increment: test-first, `make mcp-<server>-test` green; existing
  suites (`review-schemas-test`, `dataset-test`) stay green.
- Increment 4: compose contract suite green end-to-end.
- Increment 5: smoke outputs pasted (sanitized) into Runbook 10; identifier
  check before any commit that includes evidence.
- Independent read-only subagent review before phase close (Phase 2/3
  pattern).

## Exit criteria (from development-plan.md)

Contract tests pass against local compose services; each server deploys to
Cloud Run via a Makefile target and answers a smoke call.

## Out of scope

- Agents and ADK adapters (`local-agents` compose profile) — Phase 5.
- Orchestration service, turn leases, direct-MCP-client wrapper — Phase 6.
- Evaluation judge wiring — Phase 7/8.
- CI/CD pipelines — deferred to promotion (D3).
- Extension 2 (linked context stories) mock data — deferred; only the
  mapping structure is exercised (empty lists).

## Risks and controls

- **Scope creep into orchestration**: the direct MCP client used in compose
  contract tests is a test fixture only; the real wrapper (timeouts/retries
  per observability.md) is Phase 6.
- **Preparation ambiguity** (HTML flattening, quality_class derivation):
  settled with the owner in increment 0 and captured as a decision before
  server code; golden snapshots make later drift loud.
- **PDF stack weight/determinism**: library choice isolated to increment 3;
  determinism asserted by test.
- **Dataset leakage into images**: `.dockerignore` plus a build-time check
  that `dataset/expected` is absent from the image (test in increment 1,
  reused for all three).
- **Cost**: Cloud Run min 0; smoke tests then idle — no long-running
  resources; GCS near-empty buckets.

## References

- `docs/design/mcp-servers.md` (authoritative contract)
- `docs/design/schemas.md` (models incl. StoryComment/ContextStory)
- `docs/operations/repository-layout.md` (paths, Docker context rules,
  compose substitutes), `docs/operations/deployment.md`,
  `docs/operations/connectivity-identity.md` (ingress, audiences)
- `docs/design/observability.md` (error taxonomy)
- `docs-local/local-decisions.md` D3 (pipelines deferred), D9 + amendments
  (dataset identity, verbatim export, preparation step)
- `spikes/connectivity/spike_mcp/` (reference implementation patterns,
  Runbook 06 evidence)
