# Local Development Decisions (home phase)

Decisions for developing the capstone privately at home, on a personal Google Cloud
trial account (~$300 / 3 months). Target setup remains as documented in `docs/`.

## D1 — One static trial project

The design docs assume a one-day company sandbox with daily project recreation. For
the home phase we keep **one static project** for the whole development period — daily
recreation is friction with no benefit while self-funded. Terraform (see D2) keeps a
full recreate cheap if ever needed.

Checks performed at bootstrap (Phase 0):

- billing active with trial credits applied (Agent Engine / Vertex AI need it),
- Agent Engine + Vertex AI available in `europe-west4` on a trial account,
- `adk deploy agent_engine` works with local ADC.

## D2 — Terraform for infra, scripts for app releases

| Layer | Tool |
|---|---|
| APIs, service accounts + IAM, Cloud SQL instance, GCS buckets, Artifact Registry, Secret Manager skeletons | Terraform, split `envs/home.tfvars` / `envs/company.tfvars` |
| Cloud Run services (story/artifact/report/orchestration) | Terraform resources referencing built images (module per service) |
| Agent Engine deployments | `deploy/agents/<agent>/deploy.sh` (`adk deploy agent_engine`) — app-versioned resources (git SHA, env-pointer switching), deliberately not Terraform-managed |
| Cloud SQL migrations | `deploy/cloud-sql/run-migrations.sh` (forward-only SQL) — plain ordered
SQL files; Alembic considered and rejected (2026-09-05): no SQLAlchemy models
to autogenerate from, tiny slow-moving schema — revisit only if Phase 2+
schema churn makes autogeneration worthwhile |

Switching home ↔ company later = different tfvars + env templates. No Ansible —
Terraform + Makefile + runbook covers everything.

## D3 — Pipelines deferred to promotion

During the home phase: **local deploy scripts + Makefile targets + this runbook only.**
Neither GitLab CI nor Azure DevOps pipelines are maintained now. Both are written at
promotion time by translating the per-unit spec already pinned in
`docs/operations/repository-layout.md` (pipeline names, path filters, stage order
test → build → deploy-dev → smoke). The Makefile/script structure keeps per-unit
path-filter discipline so promotion is mechanical.

Rationale: solo development iterates faster from a shell; maintaining two pipeline
systems in parallel buys nothing before promotion.

## D4 — Local-first development loop

Primary loop is `deploy/docker-compose.yml` with local ADK adapters
(`deploy/compose/adapters/`), PostgreSQL and fake-GCS substitutes, and Vertex AI via
ADC (`GOOGLE_GENAI_USE_VERTEXAI=true`). GCP spend is concentrated in Phase 1 (spike),
Phase 8 (real deployment), and Phase 9 (evaluation/demo) — deliberate for the trial
budget.

## D5 — Cost hygiene (trial budget)

- Smallest practical Cloud SQL instance; Cloud Run min instances 0.
- Agent Engine resources: prune everything older than N-1 manually after the
  versioning proof is recorded (evidence first, then cleanup).
- No scheduled workloads; everything runs on demand from the runbook.
- Budget alert set on the trial project at bootstrap.

## D6 — Evaluator (judge) is not a deployed agent

The Phase 9 evaluation judge runs **non-deployed**, per `docs/operations/deployment.md`.
In the home phase it needs no dedicated service account:

- local run: Vertex AI via ADC (user identity) — no IAM changes;
- CI/pipeline run (after promotion): the deployment SA already holds
  `roles/aiplatform.user` from Runbook 03, which covers inference-only calls; a
  Cloud Build default SA would instead need that one binding granted.

A dedicated `sa-evaluator` + `roles/aiplatform.user` (reviewer-like profile:
stateless, no MCP/SQL/GCS access) is the documented fallback only if a future
spike proves the judge must be a deployed Agent Engine resource.

## D7 — Cloud SQL admin password kept in the gitignored env file

Runtime connectivity to Cloud SQL stays passwordless — IAM database
authentication only; no service ever sees a password. But PostgreSQL grants
IAM database users only CONNECT by default (and PG16 revokes CREATE on
`public`), so a `postgres` admin session is unavoidable to create schemas and
grant IAM roles their privileges. The frozen design's own migration path
(`run-migrations.sh`) hits the same bootstrap need.

Home-phase stance (Runbook 06 §2):

- the `postgres` password lives only in gitignored `infra/envs/home.env`
  (`SPIKE_DB_PASSWORD`), alongside the other project identifiers — never in
  git, Secret Manager, or any service; the file is verified ignored and
  untracked;
- it is used only for admin bootstrap sessions (schema/grant changes) — rare
  by design, since migrations inside an already-granted schema run via IAM
  database authentication (passwordless);
- rotation is recommended after the capstone/home phase ends (or whenever the
  machine is shared), not per use — the threat model is a local, single-user
  trial sandbox;
- services use IAM database authentication exclusively.

## D8 — Spike MCP service falls back to default ingress with mandatory ID-token auth

Increment-4 gate result (2026-09-05): Agent Engine's egress to Cloud Run was
rejected at the edge with `ingress = INTERNAL_LOAD_BALANCER` (404, no request
logs — the request never reached the container). The phase-1 plan anticipated
this and permits the fallback: change **only** the ingress setting to default
(`INGRESS_TRAFFIC_ALL`); the service stays non-public in practice because

- no public/all-users invoker grant exists — only `sa-facilitator` holds
  `roles/run.invoker`, so unauthenticated callers are rejected by IAM, and
- the pure-ASGI middleware requires a Google ID token whose audience equals
  the service URL (fail-closed 503 otherwise).

This matches the allowance in `docs/operations/connectivity-identity.md`.
Deferred (post-spike): private connectivity (PSC/VPC) is revisited only if
Agent Engine networking support and cost justify it.

## D9 — Dataset identity decoupled from ADO work-item IDs; JSON-backed story serving

(2026-09-07, session 13.) The free Azure DevOps org/project is an
**authoring-time tool only** — its work-item IDs are temporary references and
must not leak into the dataset as identifiers:

- The dataset's stable keys are **canonical case ids** (scenario slugs:
`clean`, `business-weak`, …, `hidden-conflict`), matching the manual test
  plans (`dataset/manual-plans/`) and the future expected files.
- An export script (Runbook 08/09, increment 1) fetches the stories from ADO
  into `dataset/stories/*.json` shaped as close as practical to a real ADO
  work-item export — and **re-keys** each story from the ADO id to its
  canonical case id (ADO id kept, if at all, as clearly-marked provenance
  metadata, e.g. `ado_source_id`).
- Story serving: the story MCP server (Phase 4) fetches stories from the
  JSON files locally; for the hosted demo the JSON is served from Google
  (mock endpoint standing in for a real ADO connection, which the demo
  project deliberately has none of). The MCP fetch path must be identical in
  both cases — only the backing endpoint differs.
- Matrix structure inside ADO (settled 2026-09-07): **one project, one area
  path per template** — root area = T1, `T2`–`T6` areas created at project
  root. Variants hang under the same Epic/Feature as their T1 originals, so
  hierarchy context is identical across templates; `System.AreaPath`
  partitions the export for free (no tag parsing, no teams, no extra
  projects). Expected files stay per scenario — every variant must pass the
  same scenario's manual plan (`dataset/manual-plans/`) unchanged.

### D9 amendment — export format and test-case identity (2026-09-08, session 14)

Owner-approved with the first export run (`dataset/tools/export_ado.py`):

- **Test case = one story in one template** (owner rule): case id is
  `<template>/<scenario>` (e.g. `t3/conflicting`) — refining the earlier
  illustrative `clean-t2` form. Two similar stories (e.g. a tags-varied
  stress duplicate) are two test cases: `t1/clean.json` and
  `t1/clean-2.json`, each with its own expected file.
- Folder layout: `dataset/stories/<template>/<scenario>.json`; epic and
  features export to `dataset/stories/context/` (hierarchy context, not
  test cases). `dataset/expected/<template>/<scenario>.json` mirrors
  `stories/` 1:1 (authored in Runbook 09 increment 3).
- File shape: envelope (`schema_version`, `case_id`, `template`,
  `scenario`, `ado_source_id`, `exported_at`) + the **verbatim** ADO
  work-item JSON under `work_item` (HTML fields as-is). Fidelity/trimming
  decisions apply to a SEPARATE preparation step against these files —
  never a transform-on-export.
- Export sanitization (identifier hygiene, not fidelity): every `_links`
  key dropped recursively (org URLs, volatile avatars); URL strings
  rewritten `dev.azure.com/<org>` → `dev.azure.com/$ADO_ORG` and the
  project GUID segment → `<project-id>`; author identity objects
  (`System.CreatedBy`/`ChangedBy`/`AuthorizedBy`/...) reduced to
  `displayName: "Story Author"` + `uniqueName: "<author>@example.com"`
  with account-resolvable ids (id, descriptor, url, imageUrl) dropped
  (owner decision: personal data must not enter git / the public mirror).
- Story→case resolution in the export: template from `System.AreaPath`,
  scenario from the provenance ids in `canonical-facts.md` (T1–T4, T6) and
  `t5-enabler-spec.md` (T5); the script aborts on any unknown id,
  missing/duplicate story, or area-path/provenance mismatch, and asserts
  the expected counts (42 stories + 3 context items).

### D9 amendment 2 — story ids and expected-file conventions (2026-09-08, session 15)

Owner-approved with the expected-file authoring (Runbook 09 increment 3):

- **`story_id` scheme**: schemas.md defines `StoryId` as `story-NN`; the
  matrix is numbered template-major: `t1/clean`=story-01 …
  `t1/hidden-conflict`=story-07, `t2/clean`=story-08 …
  `t6/hidden-conflict`=story-42. The field is backfilled into every story
  envelope (additive; `export_ado.py` to emit it on future re-exports).
- **Expected files are scenario-canonical** (collapsing the first
  per-template authoring, same session, owner decision): one file
  `dataset/expected/<scenario>.json` per scenario; the loader expands each
  to the 6 per-template test cases, deriving `case_id`/`story_id`/`template`
  from the story envelopes. Format invariance is thus enforced
  structurally — no duplicated copies to keep in sync. Cases needing
  template-specific expectations (e.g. stress duplicates) get their own
  expected file. This refines `docs/quality/mock-data.md`'s
  "`dataset/expected/<case>.json`" wording: the per-case contract still
  exists, materialized at load time.
- **Findings are semantic stubs**: runtime finding IDs (B-n/E-n/C-n) are
  reviewer-assigned and cannot be pinned in the dataset; expected files
  carry per-perspective stubs (`key`, `min_severity`, `topic`,
  `appears_in_version`, `resolved_at_turn`) plus severity ceilings. The
  Phase 9 runner asserts ID patterns/prefixes deterministically and stub
  presence via the judge.
- **`expected_turns` includes turn 1** (the opening facilitator turn), one
  entry per dialogue turn; `facilitator_turn_count` in `expected_final`
  follows the schemas.md rule that PO acceptance does not invoke the
  facilitator.
- Conflicting scenario closing variant: **variant 1** (2-turn
  conversational finalize) recorded in the expected file.

## Differences from `docs/` (summary)

| Topic | `docs/` (company) | Home phase |
|---|---|---|
| Project lifetime | one-day sandbox, daily recreation | static trial project |
| CI/CD | 8 Azure unit pipelines + evaluation | local scripts + runbook; pipelines at promotion |
| Pipeline auth | SA key in Azure secrets (WIF at production) | ADC / `gcloud auth application-default login` |
| Retention/housekeeping | project lifetime, no cleanup | manual pruning per D5 |

### D9 amendment 3 — comments and linked context stories (2026-09-09, session 16)

Design basis: `docs/design/schemas.md` StoryComment/ContextStory (owner-approved
session 16, commit `52534ef`); plan
`docs-local/plans/dataset-extensions-comments-linked-stories.md`.

- **Comments** on a story are stored in the envelope as verbatim (sanitized)
  ADO comments-API objects under `comments` (minimally validated: non-empty
  `text`; list cap 50, matching the design). Mapping to the design's
  `StoryComment {author, text, created_at}` is the **Phase 4 story-MCP
  preparation step**, not the loader's — the export stays verbatim (D9
  principle). Comments are **semantic review input** (the D9 metadata
  classification item, now resolved: they are input, not display).
- **Linked context stories**: envelope gains `linked_stories: [case_id...]` —
  references, never embedded content; each target must be an existing story
  file in the dataset (cross-file invariant enforced by the loader); no
  self-references, no duplicates, max 5 (all matching the design caps).
  `relation` (related/depends) lives in the ADO work-item relations of the
  verbatim export; the MCP maps it to `ContextStory.relation`.
- Context-only stories (referenced but not test cases) are **deferred** with
  the extension-2 mock data: their file placement and loader treatment
  (context/ widening vs template folders, expected-file absence) will be
  decided at authoring; the envelope/validator structure above already
  supports them.
- Comment **personas** (owner, session 16 spike): single anonymized
  "comment author" — one real user only; the Phase 4 story MCP will likely
  drop comment authors entirely (revisit `StoryComment.author` then).
  Comments export evidence: Runbook 08 comments-API spike (preview-only
  `7.1-preview.4`; az fallback not viable with MSA login; comments key
  omitted when empty).

### D9 amendment 4 — Phase 4 story-serving decisions (2026-09-09, session 17)

Owner decisions at Phase 4 increment 0 (plan
`docs-local/plans/phase-4-mcp-servers.md`):

- **`StoryComment.author` is kept** (resolves the amendment-3 "likely drop"
  note): the preparation step maps the single anonymized "comment author"
  persona; no `docs/` change.
- **Preparation runs at server startup, in memory**: the story MCP reads
  `/app/dataset/stories/` envelopes, flattens HTML rich-text fields to the
  design `Text` projection, and maps ADO fields to `StoryDetail` per the
  mapping table (title/status ← System fields; epic/roadmap context from
  the parent envelopes in
  `dataset/stories/context/`). Images stay dataset-agnostic; a committed
  golden snapshot pins the preparation output per story file. The export
  files remain verbatim (D9 principle unchanged).
- PDF rendering library choice is deferred to Phase 4 increment 3.
- `shared/review_schemas` 0.2.0: `StoryComment` + `ContextStory` added to
  `StoryDetail` per schemas.md (code catching up to the session-16 design
  change); test-first, suite 151 green.

### D9 amendment 5 — Dataset evaluation metadata stays outside runtime story contracts

Owner-approved 2026-09-09 during Phase 4 increment 1. `quality_class` was
removed from the public `StorySummary`/`StoryDetail` schemas and therefore
from API and MCP list results. It was a test-oracle leak: a real Azure DevOps
story does not carry its expected review outcome. The dataset envelope's
`scenario` and `dataset/expected/` contracts retain that evaluation metadata
for the Phase 9 runner only; story preparation must never map or return it.
`shared/review_schemas` is version 0.3.0; its contract test rejects a public
story payload containing `quality_class`.

## D10 — Story MCP server dual data source (production Azure, mock GCS)

Owner-approved 2026-09-09 (session 19), ahead of Phase 4 increment 1. The
owner wants the story MCP server to have a **real production path** (live
Azure DevOps) alongside the mock dataset used for testing and demos. This is
a design change, applied to `docs/design/` (schemas.md StorySource + widened
StoryId, mcp-servers.md "Dual data source", mock-data.md GCS publication,
repository-layout/deployment/tech-stack dataset-agnostic images,
connectivity-identity PAT secret) as separate atomic docs commits
(cherry-picked to `docs/initial-frozen`).

Owner decisions:

- **Selection mechanism (option a)**: optional `source` field
  (`azure`|`mock`, default `None` = deployment `STORY_SOURCE` env) on
  `ListStoriesInput`/`GetStoryInput`; explicit override is orchestration-only
  and transparent to agents. The server stays stateless; a story run is
  pinned to one source by the deployment it executes in (compose/demo =
  `mock`, production Cloud Run = `azure`). Session-pinned headers were
  rejected (ADK toolset plumbing, state in a stateless server).
- **StoryId widened** to `^(story-[0-9]{2}|ado-[0-9]{1,8})$`: `story-NN` =
  frozen mock dataset (zero-padded, unchanged), `ado-N` = live Azure work
  item; id spaces never mix; cross-source
  lookups return `STORY_NOT_FOUND`.
- **Mock dataset lives in GCS** (`gs://$PROJECT_ID-story-dataset/`), pushed
  from local via `make dataset-push` (stories + context envelopes only,
  never `dataset/expected/`); local tests/compose use a directory location
  instead of the bucket. Images are fully dataset-agnostic (no Dockerfile
  copies `dataset/`) — supersedes the D9-amendment-4 baked-image working
  assumption; startup preparation in memory is unchanged.
- **Azure path**: live REST (WIQL list, `workitems/{id}?$expand=all` +
  comments API get; the Runbook-09-proven REST access), PAT from Secret
  Manager, egress to dev.azure.com. Owner reuses the existing `rest-verify`
  PAT (Work Items: Read) from gitignored `infra/envs/ado.env`; at increment 5
  it moves into Secret Manager for the deployed service (owner may rotate it
  into a dedicated token then).
- **Evaluation guard**: evaluation and regression runs always use `mock`;
  `azure` is production/demo only (content drift would invalidate
  `dataset/expected/`).

### D10 amendment 7 — azure/Secret-Manager wiring deferred beyond Phase 4 (2026-09-10, phase-4 close)

Phase-4 completion-review finding (Important): D10 committed the PAT to
Secret Manager "at increment 5", but increment 5 deployed the story service
with `STORY_SOURCE=mock` and the `mcp-service` Terraform module has no
secret-from-Secret-Manager env support; the azure source is exercised only
by unit tests against a stub transport. Owner decision: this is a deliberate
deferral, not a gap — the production azure path (Secret Manager wiring,
`STORY_SOURCE=azure` deployment, ADO PAT rotation) is **Phase 8 territory**
(real GCP deployment / production realism). Nothing in Phases 5–7 needs it
(evaluation is mock-only by the D10 evaluation guard). Recorded so it is not
lost: the deferred work is "PAT → Secret Manager + module secret env + azure
deployment story-server vars", to be planned in the Phase 8 plan.

### D9 amendment 6 — ADO wire models extracted to `shared/ado_wire` (2026-09-10, session 20)

Owner-approved refactor, ahead of the story-server implementation: the pure
Azure DevOps wire models (`WorkItem`, `WorkItemComment`) moved verbatim from
`dataset_loader.envelope` into a new shared package `shared/ado_wire`
(dep: pydantic only), so the story-MCP preparation pipeline and the future
live `azure` source import the wire shapes without depending on the dataset
loader. `StoryEnvelope` and the dataset-specific aliases (`Template`,
`Scenario`, `CaseId`, `T1_ONLY_SCENARIOS`) stay in `dataset_loader` — the
envelope is the frozen-dataset export wrapper, not ADO wire format.
`dataset_loader.envelope` re-exports the two moved models, so all existing
test files (dataset, story, review-schemas) stayed byte-identical; new
behavior tests live in `shared/ado_wire/tests/` (Makefile `ado-wire-test`).
Consequence: story-server images ship the small `ado_wire` code package but
no longer need the loader for wire models (`prepare.py` still imports
`StoryEnvelope` from `dataset_loader` for the mock path); the D10
images-carry-no-dataset-content rule is unchanged and enforced by the
build-time check.

### D11 — report MCP bucket scope and runs-tree lifecycle (2026-09-10, increment 5)

Owner-approved deviation from connectivity-identity.md's "objectAdmin
scoped to a report prefix": GCS IAM resource-name conditions cannot express
mid-path wildcards (`runs/<run>/reports/`). `.contains()` fails CEL
compilation; an `extract()`-based condition compiles but does not grant on
`storage.objects.create` (live-verified 403). sa-report-mcp therefore gets
unconditional `objectViewer` (it must read finalized-reviews under
`runs/<run>/artifacts/`, which the old binding also missed) plus
`objectAdmin` conditioned on `startsWith('.../objects/runs/')` — the whole
runs tree, not just report prefixes. Accepted residual risk: the report
service *could* write artifact-prefix objects; mitigated by it being an
internal, orchestration-only-called service, and both servers share the
bucket by design. Same constraint resolved the lifecycle rule: the 90-day
deletion now covers the whole `runs/` tree (artifacts are per-run data
too). If a future prefix-precise mechanism appears, tighten both.

### D12 — MCP service URLs/audiences as plain Terraform env, not Secret Manager (2026-09-10, increment 5)

connectivity-identity.md lists "MCP endpoints and audiences" among runtime
values that live in Secret Manager. The increment-5 implementation injects
each service's audience (`*_SERVICE_URL`) as a plain Terraform var →
container env var instead: a Cloud Run service URL is not a secret (it is
unusable without a valid ID token), and the two-step apply pattern (URL
known only after the first apply) is materially simpler with a plain var
than with Secret Manager round-trips. Owner-approved with the review
finding; revisit on production promotion if the doc's shape is mandatory
there.

## D13 — Phase 5 agent tests use a real low-cost Gemini model (2026-09-11)

Owner decision: do not mock or script LLM responses for the agent-based
application. Agent-behavior and adapter tests call the real
`gemini-2.5-flash` model through Vertex AI in `europe-west4` on the main PC,
because validating LLM behavior is the purpose of those tests. All four agents
use that model initially and pin it in their immutable `config.yaml` files.
Deterministic local tests remain only for non-LLM behavior such as prompt
loading and SHA-256 calculation; the ADC-less dev server cannot run
agent-behavior tests.

Use ADK native structured-output enforcement backed by the shared strict
Pydantic models. Only malformed facilitator delegation output gets the
bounded corrective re-prompt loop; reviewer and synthesis validation failures
return structured errors after normal transport retries.

Use ADK `DatabaseSessionService` with the compose `postgres:16` substitute
from Phase 5 onward. This preserves deployed-shape parity; migrations for
audited application records remain Phase 6.

Keep prompts as centrally accessible static files in `prompts/`. Initial
prompts are minimal and functional; the owner reviews all four together before
their first commit. Iterate on prompt quality later from full-application test
evidence, rather than optimizing prompts prematurely in Phase 5.

Expose separate typed single-turn invocation interfaces for each reviewer and
the synthesis agent, and a separate session-scoped interface for the
facilitator. Phase 6 orchestration owns input assembly. The approved
request/response fields are frozen in the Phase 5 increment-0 hand-off spec
before adapter code is written.

## D14 — Agent packaging: four separate packages + shared agent-kit helper (2026-09-12)

Owner decision at Phase 5 increment 0 implementation start: the four agents
are four separate uv packages under `agents/<slug>/` (exactly as
`docs/operations/repository-layout.md` documents — each with its own
immutable `config.yaml` and `requirements.in`/`lock`, matching the per-unit
deploy/pipeline layout). The fail-loud `PROMPTS_DIR` loading + SHA-256 and
strict `config.yaml` parsing live in a new shared package
`shared/agent_kit` (`agent-kit` 0.1.0), following the established
`shared/mcp_ingress` pattern. `google-adk` pinned at the spike-proven 2.8.0
in each agent lock; `temperature: 0.0` / `max_output_tokens: 8192` initial
generation settings (D13 model: gemini-2.5-flash, europe-west4).

### D13 amendment 1 — Serving-safe LLM-facing output mirrors (2026-09-12)

Discovered at the increment-1 live gate: Vertex AI structured output
rejects the strict shared `ReviewReport` schema natively (400
INVALID_ARGUMENT, "schema produces a constraint that has too many states
for serving" — regex `StringConstraints`, array `max_length`s, bounded
integers, date-time formats). Owner decision: keep ADK native
`output_schema` enforcement but point it at a **serving-safe mirror model**
(plain types, identical field names) provided by `agent_kit.llm_output`;
the shared strict models remain the sole validation authority — every model
payload is validated through them unchanged at the adapter boundary, and
failures take the normal structured-error path (no corrective re-prompt for
reviewers/synthesis; the facilitator's bounded corrective loop is
unchanged). D13-3's intent (native enforcement backed by the shared strict
models) is preserved; the mirror is an implementation detail of the
Vertex serving constraint.

### D14 amendment 1 — Agent output-token cap 16384 + increment-4 envelope/dependency notes (2026-09-12, session 30)

Evidence-driven changes recorded after Phase 5 increment 4:

- **`max_output_tokens` 8192 → 16384 for all four agents**: the story-05
  synthesis merge exceeded the 8,192-token output cap (truncated,
  invalid JSON at ~10.7k chars). gemini-2.5-flash supports far more;
  16,384 leaves headroom for the facilitator's dialogue turns too.
- **`FacilitatorResponse.corrective_reprompts` (0–2)** is a recorded
  extension of the frozen facilitator response envelope (plan appendix):
  observability.md requires the counter to be recorded, and the adapter is
  the only place that knows it; orchestration persists it in
  `AgentRunRecord`.
- **`google-adk[mcp,db]`** replaces plain `google-adk` wherever toolsets
  or the DatabaseSessionService are imported (agent-kit, facilitator agent
  and adapter); `asyncpg` added for the Postgres session URL.
- **local-agents profile credential shape**: host ADC bind-mounted
  read-only + `GOOGLE_APPLICATION_CREDENTIALS`, containers run as the host
  uid (mode-600 ADC); local profile only, no SA keys, all ports loopback.
- **Agent wheels force-include `config.yaml` inside the package** (one
  shared site-packages dir would collide across agents); `load_config()`
  resolves wheel vs editable source locations.

Tool use under `output_schema` was verified empirically (Runbook 11 §4):
ADK 2.8.0 + gemini-2.5-flash invoke function tools before producing the
structured reply — the facilitator's read-only MCP toolsets are live.

## D15 — Orchestration packaging, persistence, and test seams (2026-09-13)

Owner decisions at Phase 6 opening (all six plan items approved in chat,
2026-09-13; plan: `docs-local/plans/phase-6-orchestration.md`):

1. **Packaging**: `orchestration/` as a uv package (`orchestration` 0.1.0,
   FastAPI + uvicorn, own `requirements.in`/`lock`), root-context Dockerfile
   per repository-layout.md, wired into the compose `local` profile.
2. **Persistence**: hand-written ordered SQL migrations in
   `deploy/cloud-sql/migrations/` + `run-migrations.sh` (per
   repository-layout.md), consumed by a thin asyncpg repository module —
   **no ORM**; schemas.md database constraints enforced in SQL and the
   repository, lease/claim semantics via conditional updates.
3. **Test seams (extends D13)**: deterministic orchestration tests use
   in-process fake agent clients implementing the frozen Phase 5 adapter
   invocation interface (scripted, schema-valid typed outputs /
   ErrorEnvelopes) so gates, leases, idempotency, delegation branching,
   deadline clamping, and reconciliation are truth-table testable without
   model cost or flakiness. LLM behavior is never scripted (D13 intact) —
   only orchestration's downstream agent seam is faked (same logic as
   MockTransport for the Azure source and fake-gcs for the artifact
   server). MCP servers are never faked (cheap, deterministic, real
   compose services). Real-adapter + real-Vertex live gates stay main-PC
   only; prompt/agent quality stays with live gates and Phase 9.
4. **Idempotency**: per-route key + request fingerprint + stored canonical
   response (`CanonicalOperationResult`, never signed URLs; replays
   regenerate them) as a DB claim row acquired with the lease
   (in-progress → completed); in-progress state recoverable after a crash.
5. **Signed URLs locally**: fake-gcs signed-URL emulation verified
   empirically at increment 4; fallback is an unsigned fake-gcs object URL
   in the same `ReportDownload` shape, recorded then as a local-only
   substitution (to be settled empirically, not pre-decided).
6. **Facilitator reconciliation**: the ambiguous-timeout invocation-ID
   check (agents.md § Session and invocation semantics) is implemented
   against the local adapter's Postgres session backend; mechanism
   confirmed against the actual adapter interface at increment 3, any
   divergence raised with the owner before coding around it.

### D15 amendment 1 — facilitator reconciliation mechanism and increment-3 finalize scope (2026-09-13, session 36)

Owner decisions at increment 3 opening (approved in chat):

1. **Facilitator reconciliation via adapter contract extension (option A)**:
   the frozen Phase 5 adapter contract lacked any invocation-ID tagging or
   result-inspection seam, so D15-6's mechanism was added as a recorded
   contract extension (the same mechanism used for `corrective_reprompts`):
   - `FacilitatorRequest` gains a required `invocation_id` (UUID);
   - the facilitator adapter persists one completed
     `FacilitatorResponse` per `(session_id, invocation_id)` in its
     session-backend Postgres (table `facilitator_turn_results`,
     adapter-owned runtime state, created idempotently at startup —
     outside the orchestration migrations);
   - a repeated `POST /turn` for a completed invocation returns the stored
     result without a model run (at-most-once facilitator work per
     invocation across HTTP retries; failed turns store nothing);
   - `GET /turn-result/{session_id}/{invocation_id}` exposes the stored
     result (404 = never completed; may be re-invoked);
   - orchestration derives the invocation id deterministically from the
     idempotency key (uuid5) and reconciles between facilitator attempts.
   Re-verified against Agent Engine semantics at Phase 8.
2. **Increment-3 finalize scope (option B)**: the gate engine implements
   the full precedence including `open_issues empty AND invoke=none →
   finalize`, but both finalize paths (gate outcome and `po_accepted`)
   continue into flow 3, which is increment 4. Until then they return a
   retryable 503 `UPSTREAM_UNAVAILABLE` ("finalization arrives in
   increment 4"), persist no turn state, and the claim stays in_progress
   so the same key can complete the turn after increment 4 deploys. This
   is a deliberate, temporary gap inside the closed `ErrorCode` taxonomy,
   removed by increment 4.
3. **`SESSION_LOCKED` envelope shape**: schemas.md's `ErrorBody` invariant
   (retryable ⇔ retry hint present) forces `SESSION_LOCKED` to carry
   `retryable=true` + `retry_after_seconds`; the api-contract prose
   ("non-retryable ... retry a new request, not the same turn") is honored
   by the code-specific client rule: wait for the hint, then submit a new
   request/key (not an idempotent replay). No schema change needed.

### D15 amendment 2 — increment-4 settled decisions (2026-09-13, session 37)

1. **Signed URLs locally (D15-5, settled empirically)**: fake-gcs-server
   runs `-scheme both` — HTTPS (container 4443 → host
   `${FAKE_GCS_HTTPS_PORT:-9026}`, `-public-host` matching) serves the
   signed download path without signature validation; HTTP (container
   8000 → host `${FAKE_GCS_PORT:-9025}`) keeps the artifact/report
   servers and contract tests untouched. Orchestration signs V4 URLs via
   google-cloud-storage and rewrites the host to
   `ORCH_GCS_PUBLIC_URL`; the local signer is a committed throwaway RSA
   key (explicitly not a secret) because ambient ADC user credentials
   cannot sign. Local-only substitution: download clients relax TLS
   verification (self-signed fake-gcs certificate); the
   `ReportDownload.signed_url` `HttpsUrl` shape made the previously
   contemplated unsigned-HTTP fallback impossible. Without
   `ORCH_GCS_PUBLIC_URL` the signer uses ambient credentials against
   real GCS (Phase 8 wiring, re-verify there).
2. **Finalizing sessions and turn keys**: a same-key retry of a turn
   whose flow 3 failed retryably resumes flow 3 directly from the
   durable finalize turn record (no facilitator, no duplicate turn —
   data-flow.md §2 "resumes flow 3 directly"); a new key on a
   parked/completed/finalizing session is 409 `SESSION_READ_ONLY`, and
   its just-inserted claim row is deleted so a retry of that key cannot
   arrive as an in-progress takeover. `SESSION_READ_ONLY` therefore also
   covers `finalizing` for new turn requests (finalize endpoint is the
   sanctioned recovery path) — envelope code unchanged.
3. **Signed-URL TTL**: 15 minutes (`ORCH_SIGNED_URL_TTL_SECONDS`,
   default 900) — observability.md/api-contract prescribe no value;
   recorded here as the chosen constant.

### D15 amendment 3 — increment-5 exit gate runs fully live (2026-09-13, session 38)

Owner decision at increment 5 opening (approved in chat): the Phase 6
exit-gate integration suite (`orchestration/tests/integration/`, run
via `make orchestration-integration-test`) runs **fully live** against
the compose stack with the real local adapters and real Vertex —
including park-at-10 (a real 10-turn arc steered to stay open) — rather
than a hybrid (fake agent clients for scripted outcomes) or a
live-minus-park split. Accepted cost: roughly 35–50 model calls and a
15–30 minute runtime per gate run. Consequences recorded:

1. Model-dependent behavior is steered via the PO message (the
   facilitator's documented input) but asserted only on observable
   outcomes; the gate finalize is steered with a bounded retry loop
   (max 4 steering turns) before the finalize assertion fails.
2. Scripted truth-table coverage (gate precedence, park-beats-synthesis,
   failure paths) stays in the deterministic tier with fake agent
   clients (D15-3) — the live suite covers the real-adapter paths only.
3. Sessions under test use distinct stories (story-05/06/07) so the
   one-active-run-per-story constraint cannot cross-contaminate tests.

## D16 — Phase 7 client is a Web UI, not a TUI (2026-09-11)

Owner decision (approved in chat): the Phase 7 client is a **minimal web
UI** instead of the originally designed TUI — the owner confirmed a web
interface is what will actually be needed (demo audience, no local
tooling). This is a fundamental design change, applied to `docs/`
(tech-stack.md Interface row, api-contract.md "Client interaction
states", architecture.md, repository-layout.md `webui/`, data-flow.md
participant labels, index.md) per the docs-first rule.

1. **Scope — minimal MVP, functional only**: pre-conversation story
   picker (story list; hovering/selecting an item renders the story
   preview/detail via `GET /stories/{id}` before confirmation;
   confirmation sends the story id via `POST /sessions`), chat-style
   dialogue view for PO turns (one message per `POST /turns`,
   facilitator message rendered, spinner-equivalent processing state),
   PO acceptance / finalize path, and report download through the
   regenerated signed URLs. No animations, no design system.
2. **No server-side changes**: the API contract (`api-contract.md`) is
   consumed as-is — the interaction states and client rules already
   written for the TUI apply unchanged (session-ID persistence,
   idempotency-key replay, single in-flight request).
3. **Implementation shape**: thin static HTML/JS page served by a
   small FastAPI/uv package (`webui/`, per repository-layout.md),
   compose service next to orchestration; future-extensions Item B is
   superseded by this decision. **Starting point**: the owner's
   existing chat UI in `~/projects/homelab/cv-agent`
   (`src/cv_agent/static/chat.{html,js,css}`, vanilla JS, FastAPI-
   served, with a small markdown renderer and JS tests) is reused/
   adapted — its chat shell and message rendering carry over; the API
   calls must be re-pointed to the orchestration endpoints with
   idempotency-key handling, and the story picker with hover preview
   is added. No server-side changes.

## D17 — Phase 7 Web UI increment-0 decisions (2026-09-14)

Owner decisions (approved in chat), settling the increment-0 candidates in
`docs-local/plans/phase-7-webui.md`:

1. **Packaging**: `webui/` uv package — FastAPI serving static files only
   (no business logic, no DB, no downstream clients), orchestration location
   via `ORCHESTRATION_BASE_URL` env, root-context Dockerfile, compose
   `local`-profile service next to orchestration. No proxying: the browser
   calls orchestration directly.
2. **JS test tooling**: vitest + jsdom for frontend JS tests (same setup as
   the cv-agent source project); node-based, dev-only, not shipped in the
   image.
3. **Reuse mechanics**: only the chat shell (HTML/CSS) and real source
   modules (e.g. `frontend/markdown.js`) are copied/adapted from cv-agent —
   **never generated files** (owner clarified `chat.js` there is a generated
   bundle, 3.6k lines; not hand-written source). The API layer is written
   fresh against api-contract.md.
4. **Client persistence**: session id + pending idempotency keys stored in
   `localStorage` keyed by session id, so a page reload resumes the active
   session (client rule: persist the key with the in-flight logical request).
5. **Gate driving mode — owner-driven manual browser walkthroughs**: the
   agent proposes exact steps, the owner clicks through them against the
   compose stack and reports evidence. Rationale: a UI has to be
   human-tested anyway (the reason D16 exists), and this matches the
   established live-gate protocol. No browser automation in this phase.

### D17 amendment 1 — same-origin /api reverse proxy on the webui (2026-09-15)

D17-1 said "no proxying: the browser calls orchestration directly". While
opening Runbook 13 the owner and agent found this unworkable as written:

- Orchestration has no CORS middleware and D16 forbids orchestration
  server-side changes, so direct browser→orchestration calls from the
  webui origin are blocked by the browser (different port = different
  origin).
- Orchestration had no persistent HTTP endpoint at all: Phase 6 live gates
  ran it in-process (httpx ASGI transport) against the compose adapters.

Owner decision (chosen for its fit to the future GCP deployment, where one
HTTPS load balancer routes `/api/*` to the orchestration Cloud Run service
and everything else to the webui service — same origin, no CORS anywhere):

1. **The webui FastAPI app adds a thin same-origin `/api` reverse proxy**
   to `ORCHESTRATION_BASE_URL`: pure pass-through of method, path, query,
   body, and the client-hop headers (Content-Type, Idempotency-Key,
   X-Correlation-Id); no business logic, no persistence. Unreachable
   orchestration → 503 with a retryable `ORCHESTRATION_UNREACHABLE` error
   envelope. D17-1 is amended from "static files only" to "static files +
   the /api pass-through proxy only".
2. **Orchestration becomes a compose service** (`local-agents` profile,
   proxy target for browser gates; the Phase 6 pytest suites are unchanged).
   The compose `postgres` (facilitator DB) also carries the orchestration
   tables there; migrations run on demand via `run-migrations.sh` from a
   throwaway container on the compose network (Runbook 13 has the command).
3. **Browser-side libraries are vendored as the libraries' real ESM dist
   files** (`static/vendor/`), loaded via an import map — no bundler, and
   no generated bundles (D17-3 intact: nothing we generate is committed).

## D18 — Issue-identifier lifecycle: `reopened` disposition + adapter-side check (2026-09-16)

Owner decision resolving future-extensions Item E (found at the Phase 7
increment-3 live gate, session 42): a finalized review showed issues B-1/B-2
both resolved (turn 2) and remaining open (turn 3) because the facilitator
re-used resolved ids for new concerns; the contract permitted the overlap.

Mechanism chosen (of the two candidates sketched in Item E):

1. **`reopened` disposition** added to `ResolutionDraft`/`ResolutionItem`
   (design change in `docs/design/schemas.md` + frozen cherry-pick; shared
   review_schemas version bump). Latest-wins aggregation already reflects a
   re-open; the report's Resolutions table shows the final disposition.
2. **Prompt rule**: issue identifiers are immutable; a regressed concern is
   re-opened with `reopened` on the same turn it reappears in
   `open_issues`; a new concern gets a fresh id.
3. **`decision_state` extension to the facilitator turn request** (contract
   extension recorded here, D15-6 pattern — the request contract is
   docs-local): orchestration assembles from the durable TurnRecords the
   authoritative per-turn state — the latest-wins resolution map plus the
   last delegation's open list — and renders it into the turn message
   ("Current decision state"). This is the root-cause fix: the facilitator
   previously had no structured record of past decisions and reconstructed
   state from conversation prose. The same shared helper feeds finalize-time
   aggregation, so input context and report provably agree.
4. **Adapter-side consistency check in `validate_turn_output`** (not an ADK
   callback): a `resolved`/`accepted` id in `decision_state` may appear in
   `open_issues` only if the same turn emits `reopened` for it; violations
   enter the existing bounded corrective re-prompt loop
   (`DELEGATION_VALIDATION` on exhaustion). Callbacks stay reserved for
   telemetry/authorization (Item D) — repair belongs to the proven loop.
5. **`FinalizedReview` deterministic backstop**: validator rejects a final
   state where a remaining-open id's latest disposition is `resolved`/
   `accepted` (non-retryable → rolls back to `active`).
6. **No state echoing**: the facilitator does not echo the decision state in
   its reply — typed output + rendered context suffice (owner decision;
   echoing invites drift).

Backward compatibility: dispositions and `decision_state` are per-turn
request/response data; stored TurnRecords and the compose-Postgres sessions
need no migration (orchestration derives the map from existing records).

### D18 amendment 1 — `FINAL_REVIEW_INVALID` error code (2026-09-16)

Implementing the backstop (D18 point 5) surfaced that the ErrorCode taxonomy
is a frozen Literal: the non-retryable contradiction failure gained its own
code `FINAL_REVIEW_INVALID` (503, no retry hint — the PO must re-engage the
dialogue), added to `docs/design/schemas.md` in the same D18 docs change and
to the shared `ErrorCode` literal (review_schemas 0.5.0).

### D18 amendment 2 — review findings (2026-09-16)

Independent read-only review of the D18 implementation (verdict: Ready to
proceed) found one Important, fixed in-session: the adapter rule now also
rejects a **same-turn self-contradiction** (an id `resolved`/`accepted` this
turn while still on this turn's `open_issues`) — previously such a turn
passed and the contradiction only surfaced at the finalize backstop.
Minors fixed: `_decision_state` returns `None` when no prior turns exist
(matching the documented contract), and `DecisionState.resolutions` cap
aligned to 200 (FinalizedReview's cap; avoids an unreachable construction
failure). Accepted as-is: `FINAL_REVIEW_INVALID` also covers the
pre-existing FinalizedReview validation rules (previously unhandled 500s —
broader but strictly better); the phase-5 plan appendix now records the
`decision_state` request-contract extension (D15-6 precedent).

## D19 — Issue catalog: typed descriptors for facilitator-minted issues (2026-09-16)

Owner decision (session 43, found at the Item E live gate): finalized
reports referenced bare issue ids — remaining-open lists and Resolutions
carried no titles/descriptions, and facilitator-minted ids (e.g. E-7–E-9
on story-09) had no descriptive home anywhere. Owner: complete solution,
no fallback debt. Chosen mechanism (hybrid — facilitator input +
orchestration catalog):

1. **`IssueDraft` on `FacilitatorTurnOutput.new_issues`** (id, title,
   description): required on the same turn the facilitator adds a *minted*
   id to `open_issues` — one not present in the latest synthesis
   findings/conflicts. Synthesis-born ids (B-*/E-* findings, C-*
   conflicts) keep their synthesis title/description/severity; no
   re-description (avoids drift). The adapter enforces the
   minted-id-needs-descriptor rule deterministically in
   `validate_turn_output` (it holds the synthesis report in the request);
   violations enter the corrective re-prompt loop (D18 pattern, proven
   live).
2. **`TurnRecord.new_issues`** accumulates the stamped drafts.
3. **`FinalizedReview.issues`** (`IssueEntry`: id, title, description,
   severity where known, source `synthesis`|`facilitator`, cap 400),
   assembled by orchestration at finalize: latest-synthesis findings +
   conflicts ∪ accumulated facilitator drafts. Validator rejects any
   referenced id (resolutions ∪ remaining-open) without a catalog entry —
   a bare unexplained id can no longer reach a rendered report.
4. **Renderer** gains an "Issues" catalog section and annotates
   Resolutions/Remaining-open rows with issue titles.
5. `remaining_open_issues` stays a list of ids (annotation happens at
   render); stored artifacts stay small.

review_schemas version 0.5.0 → 0.6.0. Backward compatibility: old
sessions (no `new_issues` in turn records) finalize with the
synthesis-only catalog; ids absent from both sources now fail the
completeness validator (previously they rendered bare — the defect
itself).

### D19 amendment 1 — review findings (2026-09-16)

Independent read-only review of the D19 implementation (verdict:
Needs-fixes → all findings fixed in-session): malformed synthesis
artifact content during the catalog fetch is now classified per the
data-flow §3 table (deterministic validation failure → non-retryable,
rolls back to active; previously an unhandled 500 leaving the session
stuck in `finalizing`); the fetch runs inside the failure-handling try;
catalog overflow raises a clear FINAL_REVIEW_INVALID instead of silent
truncation into a deferred validator failure; `FinalizedReview.issues`
gained a uniqueness validator and reuse-previous turns may not mint
issues (matching the no-resolutions rule). Accepted as-is: conflicts
render with the synthesized title "Conflict {id}" (synthesis conflicts
have no title field); pre-D19 active sessions with prose open_issues
(story-01/-04/-06 in the compose Postgres) may fail the completeness
validator at finalize — the defect surfacing, expected; increment 4
uses a fresh session.

### D19 amendment 2 — live-gate findings (2026-09-16, session 44)

The D19 live gate (story-05) surfaced two implementation gaps, both
fixed in-session (evidence: Runbook 13 §D19 live gate):

1. **Serving-safe mirror gap**: the facilitator's ADK
   `output_schema` mirror (`ServingSafeFacilitatorTurnOutput`) was not
   extended for D19 — no `new_issues` field, so Vertex structured
   output could never emit an IssueDraft (byte-identical replies across
   corrective re-prompts at temperature 0 were the diagnostic signal).
   Fix: `MirrorIssueDraft` + `new_issues` on the mirror.
2. **Catalog sourcing (owner decision)**: the catalog is now the
   **union of every synthesis version the session produced, latest
   version winning on collision** — a later synthesis legitimately
   drops findings the reviewers stopped reporting, but ids still
   referenced by the final review (resolved mid-session) must keep
   their descriptors. Chosen over lazy backfill for report quality.
   Applied to `docs/design/schemas.md` (issue-catalog paragraph);
   implementation in `orchestration/finalization.py`.

Supporting (kept): facilitator prompt `new_issues` worked example;
descriptor-validator rejection carries the inline JSON shape (flows
into the corrective re-prompt). Gate verdict: **PASS** on story-05 —
F-1 minted with a same-turn descriptor, Issues section present, all
Resolutions/Remaining-open rows titled, no bare ids.

## D20 — Live processing-stage progress (session 45, 2026-09-16)

Owner decision (chat): implement future-extensions **Item F** with
**option (a) — server-persisted stage marker + read-endpoint polling**
(chosen over SSE as too heavy and client-side timers as dishonest).
The webui debt items (Runbook 13 §D19) are fixed in the same pass.

1. **Contract**: `sessions` gains an ephemeral nullable `processing_stage`
   column (migration 0003; values `reviewing`, `synthesizing`,
   `facilitator`, `delegating`, `finalizing`), deliberately **not** part
   of `SessionRecord` (live view state, not durable truth). Exposed on
   `SessionSummary`/`SessionDetail` (review-schemas 0.7.0) so a client
   may poll `GET /sessions` / `GET /sessions/{id}` while its synchronous
   POST is outstanding. Advisory only; docs updated in
   `docs/design/schemas.md` + `api-contract.md` (atomic docs commit +
   frozen cherry-pick due).
2. **Orchestration**: flows 1/2/3 publish their current pipeline position
   (set before each long step) and clear it on completion and on failure
   (finally under the lease for turns; try/except wrapper for flow 1).
3. **Webui**: stage placeholders are ephemeral chat bubbles
   (`.message-progress`, never persisted, never in history replay),
   updated by polling the session detail while the POST is outstanding
   and replaced by the real reply on completion. Flow-1 discovery: the
   picker polls the session list for the story's *processing* session
   (one-active-per-story makes it unambiguous; a stale active session
   has a null stage → no fake progress) and opens the session view early
   in a read-only passive mode.
4. **Debt fixes**: (1) a failed turn removes the optimistic PO bubble and
   restores the text to the composer; (2) opening a session clears any
   stale status banner; (3) the turn body is persisted next to the
   idempotency key (`pending:turn:{id}:body`) and a mid-turn reload
   re-issues the same logical request (same key → canonical replay
   server-side); legacy key-only pending keys are cleared (no body to
   re-issue).

## D21 — Post-delegation facilitator summary turn (Item G, 2026-09-17)

Owner decision (chat, session 46): implement future-extensions **Item G** —
a delegated dialogue turn becomes **facilitator → reviewer(s) → synthesis →
facilitator (second call) → PO**. Open decisions resolved:

1. **Presentation: option (a)** — the default chat view shows **only the
   final (second-call) reply**; the pre-delegation reply is persisted as
   `delegation_rationale_reply` (TurnResponse / TurnView / TurnRecord /
   CanonicalTurnResult) and is audit/report-appendix material.
2. **Prompt rule**: the facilitator is explicitly instructed that its
   pre-delegation reply is **not visible to the PO/user**, so the second
   reply must repeat any important findings from the first alongside the
   re-review summary (what was resolved, what remains).
3. **Gate precedence on the final output**: the "synthesis produced ⇒
   continue" rule (old data-flow gate 3) is removed — the second call has
   already evaluated the fresh synthesis, so a delegated turn with empty
   `open_issues` and `invoke=none` in its **second** output finalizes in
   the same turn. `po_accepted` and park-at-10 unchanged.
4. **Turn accounting**: a delegated turn still counts as **one**
   facilitator turn (once per turn, not per invocation); two invocation ids
   per delegated turn, each with its own reconciliation and corrective
   re-prompt budget; the second call cannot chain a new delegation within
   the same turn (executes on the next PO turn).
5. **Cost accepted**: one extra facilitator model call per delegated turn.

Docs applied (this session): `docs/design/data-flow.md` §2 (prose, mermaid,
regenerated ASCII from `flow2.puml`), `agents.md`, `api-contract.md`,
`schemas.md`, `architecture.md`, `observability.md`, `example-interaction.md`
+ `diagrams/flow2.puml`. Review-schemas package bump (0.7.0 → 0.8.0) and
implementation are follow-up work (with/after Phase 8 planning).

## D22 — Abandon session (explicit park-now) + historical sessions view (2026-09-12)

Owner decision (chat, session 49), triggered by the increment-4 walkthrough:

1. **Abandon endpoint**: `POST /api/v1/sessions/{id}/abandon` (empty body +
   Idempotency-Key) parks an `active` or `finalizing` session immediately —
   no facilitator/model call, no report. Motivation: a stuck session
   (permanently broken upstream / missing lineage artifacts) otherwise has
   no exit and locks its story forever (one-active-run-per-story).
   Semantics: one atomic transition parks the session **and** its story run
   (story released for a new session; history stays read-only);
   `facilitator_turn_count` unchanged; terminal states → 409
   `SESSION_READ_ONLY`; in-progress claim under the lease → 409
   `SESSION_LOCKED` retryable (lease TTL 6 min); unknown → 404; same-key
   replay returns the stored canonical response. Response:
   `AbandonSessionResponse {session_id, state:"parked"}` — no new error
   codes. `finalizing` is explicitly allowed (a stuck retryable
   finalization is a target case).
2. **One active session per story stays** (owner: "is ok to have only one
   session per story") — parallel active sessions per story were considered
   and rejected for MVP; not recorded as a future extension.
3. **Historical sessions view** (webui-only, no design change): the picker
   gains a past-sessions list from `GET /sessions` (parked/completed,
   multiple sessions per story), opening the existing read-only session
   view.
4. **Deferred webui debt (owner decision)**: the passive processing view
   does not render the pending PO bubble on mid-turn reload in the owner's
   browser despite the session-49 fix (test-covered server-side; cause
   unresolved — possibly browser caching); recorded as minor debt, not
   MVP-blocking.

Docs applied (this session): `api-contract.md` (endpoint tables + abandon
section), `schemas.md` (`AbandonSessionResponse`), `architecture.md`
(session lifecycle bullet). Implementation (orchestration + webui) is
follow-up work in a fresh session; Phase 7 close-out follows it.

## D23 — GitHub-dark Web UI presentation pass (2026-09-12)

Owner request before Phase 8: retain the completed Phase-7 behavior and API
contract while making the interface more pleasant with minimal UI-only work.
The static Web UI uses a compact GitHub-dark palette, improved control and
content hierarchy, responsive small-screen layout, clearer chat bubbles, a
green send action and reachable-backend status, a blue-accented primary
story-selection panel, and the footer `@ 2026 Marcin Żak / mmz.sh` with
`mmz.sh` linked to `https://mmz.sh/`.
No server, API, workflow, or animation changes are in scope.

## D24 — Phase 8 deployment decisions (2026-09-21)

Owner decisions (chat, Phase 8 planning session), all recorded in
`docs-local/plans/phase-8-gcp-deployment.md`:

1. **No CI/CD this phase**: deploys run from the local machine via
   Makefile targets + runbook; `pipelines/*.yml` stay a designed intent.
2. **Web UI deployed** to Cloud Run, served under the owner's Cloudflare
   `mmz.sh` zone via a subdomain (e.g. `story-review.mmz.sh`); exact
   routing (Cloud Run custom-domain mapping vs Cloudflare-proxied CNAME)
   settled empirically at the deployment increment. Orchestration is
   reached only through the webui same-origin `/api` proxy (D17-1 shape).
3. **Anonymous multi-user scoping, full**: `user_id` on sessions/story
   runs (migration 0005); one-active-session-per-story per user; webui
   90-day sliding cookie auto-refreshed on visit, forwarded as a header
   through the proxy; no auth for MVP (budget alert backstop; Cloudflare
   Access/rate-limiting later if needed). Retention 90 days via an
   owner-run `make` purge command — no scheduled job.
4. **Item D scope: facilitator-first** — telemetry callbacks + 50%/75%
   context policy on the facilitator only; stateless agents later via the
   shared helper.
5. **AE retention per D5**: keep >= N-1 versions; superseded Agent Engine
   resources pruned after the versioning proof (owner-run destructive).

### D24 amendment 1 — Facilitator AE session backend (2026-09-21)

Owner decision (chat, Phase 8 planning session): the deployed facilitator's
ADK session store is the **Cloud SQL PostgreSQL** `DatabaseSessionService`
(IAM database login, per connectivity-identity.md) — the same engine the
local adapter already uses via the compose Postgres. Agent Engine's managed
session option is not adopted; local runs keep using the local Postgres
substitute. Closes the increment-3 open design point in
`docs-local/plans/phase-8-gcp-deployment.md`.

### D24 amendment 2 — AE-side lineage guard deferred (2026-09-13)

Recorded deferral (Phase 8 increment 3, per plan): on Agent Engine the
facilitator's story/artifact MCP toolsets are wired **read-only via
`tool_filter`** (fetch tools only; no artifact-save tool exposed), but the
contextvar-bound lineage guard (per-invocation artifact-write authorization
used by the local adapter) has **no Agent Engine equivalent** — AE invokes
the agent without a request-scoped context the guard can bind to. The
enforcement point moves to the increment-4 invocation contract
(orchestration → AE): write paths are either not delegated at all
(read-only toolset) or validated at the orchestration boundary. Decision
with the owner due when increment 4 fixes the invocation contract shape.

## D25 — Increment 4: all-agent AE invocation + session-store reconciliation (2026-09-14)

Owner decisions (chat, increment-4 planning):

1. **All four agents** are invoked via Agent Engine from the deployed
   orchestration (not facilitator-first) — all engines are deployed anyway.
   Env-selected pointers (`ORCH_AGENT_MODE=http|ae`) keep the local/compose
   HTTP-adapter path as the deterministic tier.
2. **Reconciliation = option B**: on a doubtful facilitator retry, the
   orchestration reads the facilitator's ADK session events (Cloud SQL
   `facilitator` DB, over `:query`) and matches a prior reply by
   `invocation_id` before re-invoking — at-most-once facilitator execution.
   Reviewer/synthesis invocations stay at-least-once (duplicates only cost
   money, no conversation-state corruption). Orchestration-side TurnRecord
   dedup is the fast path before any AE read-back.
3. Increment-4 breakdown recorded in
   `docs-local/plans/phase-8-gcp-deployment.md` §4 (includes the
   facilitator clean-tree redeploy and the Runbook 06 gotchas 3–4 gate
   checklist).

### D25 amendment 1 — reconciliation matcher and reviewer user_ids (2026-09-14)

Recorded at the increment-4 review (doc/code alignment): the option-B
reconciliation matcher keys on the **rendered turn marker** ("This is
turn <n>", digit-bounded so turn 1 never matches turn 10), not on
`invocation_id` — the rendered facilitator message does not embed the
invocation id, and turn numbers are unique per session with the turn
lease serializing writers, so the last own-turn user message identifies
the invocation in doubt. Reviewer/synthesis AE invocations use a
**per-invocation random user_id** (stateless single-shots must not share
one growing AE conversation).

## D26 — Purge docs/source from git history (2026-09-14, owner decision)

The two capstone source files (`docs/source/evaluation.md`, `topic.md`)
came from outside the repo and must stay **local only**. Owner decision:
ignore the directory **and rewrite the full history** to remove the path
(`git filter-repo --invert-paths --path docs/source`), an explicit
exception to the standing "no history rewrites" rule.

Executed (dev server, owner approved force push): `.gitignore` entry
committed first; filter-repo across all branches (271 commits parsed);
files restored locally (ignored, untracked); remote re-added; `main`,
`docs/initial-frozen`, `dev-server/session-23` force-pushed. Backup
bundle `/tmp/capstone-pre-filter.bundle` (temporary; owner holds
independent copies of the files).

**Consequence (standing)**: every commit hash recorded in HANDOFF,
runbooks, and local-decisions **before 2026-09-14 is stale** — the git
log is the authoritative record; recorded hashes should be read as
historical labels, not resolvable ids. `docs/initial-frozen`'s freeze
commit label (`d5cb413`) is likewise stale; the branch tip is the
reference.

## D27 — Live signed URLs via IAM signBlob (2026-09-16, owner-approved fix)

`docs/design/mcp-servers.md`'s implicit Phase-8 assumption that
orchestration's ambient Cloud Run credentials can sign V4 report URLs
is unimplementable as written: Cloud Run ADC is token-only (no private
key), so client-side V4 signing raises AttributeError. Resolution
(implementation deviation recorded here, no design change): the signer
uses a keyless IAM `signBlob`-backed Signing credential as
sa-orchestration, which already holds `roles/iam.serviceAccountTokenCreator`
on itself (infra); `ORCH_SIGNER_EMAIL` is passed explicitly by the
deploy script (metadata `default` quirk), and startup `warm_up`
performs one real signBlob call (fail-loud). Local/compose keeps the
fake-gcs throwaway-key path unchanged.

**D27 amendment 1**: report MD objects are uploaded to GCS as
`text/markdown; charset=utf-8` (wire `ArtifactReference.content_type`
literal stays `text/markdown` per schemas.md); the PDF writer
transliterates the em dash to ` - ` before the lossy latin-1 mapping
(readable PDFs instead of `?`).

**Open item**: AE-side facilitator MCP toolsets may still fail session
creation (metadata `default` account in signBlob; traceback seen in
ReasoningEngine logs) — `tool_call` telemetry and tool use inside AE
unverified; investigate before relying on facilitator tools in AE mode.

**D27 amendment 2**: the D27 open item is closed. AE-side audience ID
tokens for the facilitator MCP toolsets are minted via the **metadata
identity endpoint** (`compute_engine.IDTokenCredentials(
use_metadata_identity_endpoint=True)`) — google-auth's default path
signs a JWT through the IAM signBlob API as `service_account_email`,
which Agent Engine compute credentials report as `"default"` (IAM 400).
No IAM permissions change; the attached sa-facilitator is untouched.
Incidentally learned and fixed at the same gate: ADK invokes canonical
`after_tool` callbacks with keyword `tool_response=` (not positional
`result`), and the AE toolset connect timeout is 30 s (Cloud Run
scale-to-zero cold starts exceed 10 s). Facilitator tool use and
`tool_call` telemetry verified live end-to-end (runbook 14 §D27 open
item closed).

## D28 — 75% context compaction mechanism (facilitator-side callback)

Owner decision (chat, options reviewed): the Item D remainder (typed
summary at 75% context, observability.md) is implemented **inside the
facilitator agent** as a `before_model` ADK callback — not
orchestration-side (would cross the facilitator-owned session-store
boundary, fits poorly with D25).

Mechanism (shared/agent_kit/compaction.py):
- telemetry `after_model` persists the context classification in ADK
  session state (`context_level`);
- `CompactionCallbacks.before_model` at level `summarize`: calls an
  injected summarizer (one structured-output google-genai call, the
  agent's configured model), validates the strict-schema
  `ConversationSummary` (unresolved issues, decisions, story/run IDs,
  artifact references, open points — all mandatory non-empty), stores
  the checkpoint in session state, and rewrites the model request
  contents to `[summary, *last 4 contents]`; a stored checkpoint is
  re-applied on later turns without a second summary call;
- **Implementation nuance vs observability.md wording**: session-store
  events are NOT deleted — they remain the audit record; the model's
  effective context is what gets compacted. On summarizer/validation
  failure the original contents are kept (a structured
  `compaction_failed` event is logged) rather than surfacing a
  retryable error — the failure mode here can only skip compaction,
  never drop context, which preserves the design's safety intent.
- `DEFAULT_CONTEXT_TOKEN_LIMIT` (1,048,576, gemini-2.5-flash) makes the
  policy live by default; explicit injection still wins.
- Typed summary stays inside the facilitator (no wire contract → no
  review-schemas/schemas.md change needed).
- Deployment note: wired into both the local runner and the AE root
  agent, but the live engine predates it; ships with the increment-7
  versioning-proof redeploy (it cannot trigger live in practice:
  10-turn cap, ~3k-token prompts vs 1M limit).

## D29 — Phase 9 scope: evaluation-driven tuning, demo deferred (2026-09-16, owner decision)

1. The **live demo is postponed** until the whole evaluation suite passes
   (all required dataset cases, deterministic + judged, local and dev). The
   demo becomes the opening item of the next phase.
2. **Tuning the existing stories is in scope**: the 45-case matrix
   (stories, expected files, manual plans) is iterated so the dataset better
   represents all scenarios the evaluation must prove. Story edits happen in
   the ADO source of truth + re-export, never hand-edited JSON.
3. **Agent prompt tuning is in scope**: evaluation failures attributable to
   prompt wording are fixed in `prompts/*.md` and re-proven by the suite.
   Consistent with D24-1: the evaluation runs as a local make target, no
   CI/CD (`pipelines/evaluation.yml` stays a documented intent).

Plan: `docs-local/plans/phase-9-evaluation.md`; development-plan Phase 9
scope/exit criteria updated accordingly.

## D13 amendment 2 — evaluation-driven model bump: reviewers + facilitator on gemini-2.5-pro (2026-09-16, owner decision)

Phase 9 increment 3 evidence (Runbook 15 §Increment 3, runs 6–11):
after two targeted prompt rounds, `gemini-2.5-flash` plateaued on
severity calibration, delegation routing, and open-issues convergence
while the same rounds' MCP-evidence fix landed — an instruction-following
limit, not a prompt-wording gap. Owner approved the experiment "pro on
reviewers + facilitator"; the improvement was decisive and the change
stays: business-reviewer, engineering-reviewer, facilitator
`config.yaml` → `gemini-2.5-pro` (synthesis remains flash). Config files
carry the amendment note. Cost consequence: reviewer/facilitator tokens
bill at pro rates (local + dev).

## D13 amendment 3 context — delegation assertions read executed evidence (2026-09-16)

Not a model change: the evaluation suite's delegation assertion now
derives routing from what executed in the turn (review versions ≥ 2,
`based_on_extra_context`) instead of `TurnRecord.delegation`, because
the recorded field is by design (Item G/D21) the post-delegation
summary output whose invocation is a next-turn intent. Suite-side
reading of evaluation-tests.md ("selected reviewer routing exactly
matches the scripted PO clarification"); no schema or orchestration
change, expected files unchanged.

## D13 amendment 4 context — story-01 second enrichment: email-failure scope (2026-09-16, owner decision)

Run-19 plateau: gemini-2.5-pro persistently graded "email delivery
failures other than hard bounces undefined" (AC3) as a `minor` story gap
despite a prompt rule, a worked example, and temperature 0.0. Owner chose
the D-b pattern over further prompt rounds: ADO id 5 PATCH → rev 6, Scope
sentence pinning non-hard-bounce delivery failures to the existing email
platform's standard handling (out of scope). Re-exported (dataset churn
mechanical); canonical-facts clean section records the fact. Evidence:
Runbook 15 §Increment 3 part 2, runs 19–20.
