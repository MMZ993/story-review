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
