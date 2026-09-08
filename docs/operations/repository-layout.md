# Repository Layout

One Azure DevOps monorepo. Every deployable unit has a canonical slug, an independent
pipeline, and an independently versioned deployment. Paths below are the planned,
canonical locations.

## Structure

```text
capstone_project/
├── prompts/
│   ├── facilitator.md
│   ├── business-reviewer.md
│   ├── engineering-reviewer.md
│   ├── synthesis.md
│   └── judge.md                       # evaluation-only; not an Agent Engine deployment
├── agents/
│   ├── facilitator/
│   ├── business-reviewer/
│   ├── engineering-reviewer/
│   └── synthesis/                     # each: source, config.yaml, requirements.in/lock
├── mcp_servers/{story,artifact,report}/ # source + Dockerfile per Cloud Run service
├── orchestration/{app,Dockerfile,requirements.lock}/
├── shared/review_schemas/             # versioned Python package (pyproject.toml)
├── dataset/
│   ├── stories/*.json
│   └── expected/*.json                # evaluation judge only
├── tui/
├── tests/
│   ├── {unit,contract,integration}/
│   └── evaluation/{config.yaml,...}     # pinned judge model/settings and runner
├── deploy/
│   ├── bootstrap/bootstrap.sh
│   ├── agents/<agent>/{deploy.sh,.env.example}
│   ├── cloud-run/<service>/{deploy.sh,.env.example}
│   ├── cloud-sql/{migrations/*.sql,run-migrations.sh}
│   ├── compose/adapters/{facilitator,business-reviewer,engineering-reviewer,synthesis}/
│   ├── docker-compose.yml
│   └── env/.env.example
├── pipelines/
│   ├── agents-{facilitator,business-reviewer,engineering-reviewer,synthesis}.yml
│   ├── services-{story,artifact,report,orchestration}.yml
│   └── evaluation.yml
├── .dockerignore                       # excludes expected data except evaluation builds
├── .gitignore                          # excludes build/ staging contexts
└── pyproject.toml
```

Canonical agent slugs are `facilitator`, `business-reviewer`,
`engineering-reviewer`, and `synthesis`. These exact slugs are used for prompt files,
agent directories, `deploy/agents/<agent>/`, and Agent Engine deployment names; pipeline
files use the `agents-`/`services-` prefixes defined below. Cloud Run service slugs are `story`, `artifact`, `report`, and `orchestration`.

## Prompts and agent build staging

Prompts are UTF-8 static data, never inline source. A deployed agent loads only
`PROMPTS_DIR/<agent>.md`; `PROMPTS_DIR` defaults to the runtime-safe absolute path
`/app/prompts`, never `./prompts`. Startup reads and validates the required UTF-8 file,
fails fast if it is absent or invalid, computes its SHA-256, and retains that text and
hash immutably for the life of the process. Each `AgentRunRecord` records that hash in
`prompt_sha256`, in addition to the deployed git tag/SHA. The judge uses
`prompts/judge.md` only in evaluation and is not loaded by or deployed with an agent.

`deploy/agents/<agent>/deploy.sh` runs from the repository root and creates the ignored,
self-contained agent path `build/agent-engine/<agent>/`. It copies the **contents** of
`agents/<agent>/` (including immutable model `config.yaml`) to that path, the one prompt to
`build/agent-engine/<agent>/prompts/<agent>.md`, and the shared package to
`build/agent-engine/<agent>/review_schemas/`. It exports the reviewed
`requirements.lock` as the staged `requirements.txt` expected by `adk deploy`; that lock
installs `./review_schemas` by local path.

The script invokes `adk deploy agent_engine` with the staged directory as `AGENT_PATH`,
not the source agent directory. The resulting runtime maps that staged root to `/app`, so
`PROMPTS_DIR=/app/prompts` is absolute and stable. Every independently deployed Agent
Engine image therefore contains its exact prompt and shared-package version.

A change to an agent's own prompt, model `config.yaml`, or code triggers that agent's
pipeline and `evaluation.yml`; a change only to `prompts/judge.md` triggers
`evaluation.yml` only,
never an agent redeploy.

## Shared package and dataset

`shared/review_schemas` has its own semantic package version in its `pyproject.toml`.
Each deployable image stages that package from the same commit, pins its resolved version
in its unit-specific `requirements.lock`, and installs only from that lock during build.
A shared-schema change bumps the package version and triggers every consumer pipeline;
registry publishing is deferred.

Cloud Run Docker builds use the repository root as context:
`docker build -f mcp_servers/<service>/Dockerfile .` (and equivalently for
orchestration). Dockerfiles copy only their service source plus
`shared/review_schemas`, `shared/ado_wire`, and — for the story server only —
the `dataset/loader` **code** (the export-envelope parser the mock source
reuses; D9 verbatim-export principle). No Dockerfile copies any part of
`dataset/` other than that loader package, and no dataset *content*
(`dataset/stories`, `dataset/expected`) ever enters an image — each
Dockerfile enforces this with a build-time check. The story
server is dataset-agnostic: at startup it fetches the frozen mock dataset from
GCS (`gs://$PROJECT_ID-story-dataset/`, published via `make dataset-push` —
see [../quality/mock-data.md](../quality/mock-data.md)) or reads live Azure
DevOps (deployment `STORY_SOURCE`). Expected files live only in
dataset git, are never uploaded to the bucket, and must not reach any runtime
image. Artifact and report images receive no dataset. This keeps expected
outcomes accessible solely to the evaluation judge.

## Local compose

`deploy/docker-compose.yml` has a `local` profile for orchestration, MCP services,
PostgreSQL, and a GCS-compatible storage substitute. Its `local-agents` profile uses
the four adapters in `deploy/compose/adapters/` to run ADK agents locally against the
same interfaces; it does **not** run Agent Engine in Compose. Vertex AI is the sole
external dependency in local evaluation runs.

Concrete substitutes:

- **Cloud SQL** → `postgres:16` container; migrations applied by the same
  `run-migrations.sh` before the suite starts, so the schema under test is the deployed
  schema.
- **GCS** → `fsouza/fake-gcs-server` with the artifact and report buckets pre-created;
  services point at it via the same storage-library endpoint configuration, so no
  production code path differs.
- **Agent Engine** → each adapter wraps the agent's actual ADK agent (same source,
  prompt, and `config.yaml`) behind the same invocation interface the orchestration
  uses for Agent Engine calls (single-turn run / session-scoped run, typed outputs,
  structured errors), so switching between local and deployed targets is a
  configuration change only.
- **Secret Manager / IAM** → plain environment variables from
  `deploy/env/.env.example`; MCP service-account ingress checks are disabled only in
  the local profile.
- **Report PDF rendering** → the report image's renderer runs unchanged; it has no
  GCP dependency beyond object storage (the fake above).

## Deployment manifests and pipelines

`deploy/cloud-run/<service>/deploy.sh` and its `.env.example` are the Cloud Run deploy
manifests; Dockerfiles alone are not manifests. Agent Engine deploy manifests are
`deploy/agents/<agent>/deploy.sh` and `.env.example`. Cloud SQL schema changes are
ordered SQL files in `deploy/cloud-sql/migrations/`, applied by
`deploy/cloud-sql/run-migrations.sh`. `deploy/bootstrap/bootstrap.sh` provisions APIs,
Cloud SQL, GCS, IAM, and the Artifact Registry repository.
Templates contain identifiers and Secret Manager resource names only, never secret
values.

There is exactly one deployment pipeline per unit, with these path filters:

| Pipeline | Include paths | Environment |
|---|---|---|
| `agents-facilitator.yml` | `agents/facilitator/**`, `prompts/facilitator.md`, `shared/review_schemas/**`, `deploy/agents/facilitator/**` | `dev` |
| `agents-business-reviewer.yml` | `agents/business-reviewer/**`, `prompts/business-reviewer.md`, `shared/review_schemas/**`, `deploy/agents/business-reviewer/**` | `dev` |
| `agents-engineering-reviewer.yml` | `agents/engineering-reviewer/**`, `prompts/engineering-reviewer.md`, `shared/review_schemas/**`, `deploy/agents/engineering-reviewer/**` | `dev` |
| `agents-synthesis.yml` | `agents/synthesis/**`, `prompts/synthesis.md`, `shared/review_schemas/**`, `deploy/agents/synthesis/**` | `dev` |
| `services-story.yml` | `mcp_servers/story/**`, `shared/review_schemas/**`, `deploy/cloud-run/story/**` | `dev` |
| `services-artifact.yml` | `mcp_servers/artifact/**`, `shared/review_schemas/**`, `deploy/cloud-run/artifact/**` | `dev` |
| `services-report.yml` | `mcp_servers/report/**`, `shared/review_schemas/**`, `deploy/cloud-run/report/**` | `dev` |
| `services-orchestration.yml` | `orchestration/**`, `shared/review_schemas/**`, `deploy/cloud-run/orchestration/**` | `dev` |
| `evaluation.yml` | `prompts/**`, `agents/**` (including model configuration), `dataset/**`, `tests/evaluation/**` | `dev` evaluation target; all required cases must pass |

Each pipeline also includes its own YAML path so pipeline-definition changes are tested.
Shared-package changes fan out to all consumer pipelines; root tooling changes run the
repository validation pipeline without forcing unrelated deployments. Unit and contract
checks run on each unit pipeline; evaluation runs for prompt, model, or agent-code
changes. No pipeline uses a `staging` environment name.
