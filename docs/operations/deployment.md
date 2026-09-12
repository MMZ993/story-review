# Deployment

## Google Cloud layout

| Resource | Deployment name | Manifest | Runtime |
|---|---|---|---|
| FastAPI orchestration | `orchestration` | `deploy/cloud-run/orchestration/deploy.sh` | Cloud Run |
| Facilitator | `facilitator` | `deploy/agents/facilitator/deploy.sh` | Agent Engine |
| Business Reviewer | `business-reviewer` | `deploy/agents/business-reviewer/deploy.sh` | Agent Engine |
| Engineering Reviewer | `engineering-reviewer` | `deploy/agents/engineering-reviewer/deploy.sh` | Agent Engine |
| Synthesis & Conflict Resolver | `synthesis` | `deploy/agents/synthesis/deploy.sh` | Agent Engine |
| Story MCP | `story` | `deploy/cloud-run/story/deploy.sh` | Cloud Run |
| Artifact MCP | `artifact` | `deploy/cloud-run/artifact/deploy.sh` | Cloud Run |
| Report MCP | `report` | `deploy/cloud-run/report/deploy.sh` | Cloud Run |
| Session store | Cloud SQL PostgreSQL | `deploy/cloud-sql/migrations/*.sql` | Cloud SQL |
| Artifacts | configured bucket | bootstrap + service env templates | GCS |
| Runtime secrets | per-service secret names | bootstrap + env templates | Secret Manager |

- Region: `europe-west4`; identifiers and Secret Manager resource names are supplied
  through `deploy/**/.env.example` templates. Secret values are never committed or
  passed as plain pipeline variables. Runtime service accounts receive only the specific
  `secretAccessor` grants they require; Cloud SQL prefers IAM database authentication.
  Connectivity paths, per-principal grants, MCP ID-token audiences, GCS signing
  permissions, and pooling are specified in
  [connectivity-identity.md](connectivity-identity.md).
- Agent scripts stage from the repository root before `adk deploy agent_engine`: each
  build includes its agent source, immutable model config, UTF-8 prompt, and
  `shared/review_schemas`. `PROMPTS_DIR=/app/prompts` is set at runtime. The FastAPI
  runtime service account invokes the facilitator, reviewer, and synthesis Agent Engine
  resources; the facilitator's service account reaches only the read tools of the
  story/artifact MCP servers. Details are in
  [repository-layout.md](repository-layout.md).
- Cloud Run scripts build from repository root (`-f mcp_servers/<service>/Dockerfile .`)
  so service images can copy the shared package. No image copies dataset content:
  the story server fetches the mock dataset from GCS at startup (or reads
  Azure DevOps via `STORY_SOURCE=azure`); expected outcomes never enter
  a service image or the dataset bucket.
- `deploy/cloud-sql/run-migrations.sh` applies ordered migrations before an application
  deploy that requires them.
- FastAPI is reachable via service-account ingress, or via an authenticated demo route
  for the live demo; root `/health` stays unauthenticated. The demo Web UI (deployed
  Cloud Run service reaching orchestration through its same-origin `/api` proxy) is
  intentionally unauthenticated: the client generates a UUID v4 user id, persists it
  as a long-lived browser cookie (refreshed on visit), and sends it as `X-User-Id`
  (see [../design/api-contract.md](../design/api-contract.md)). That identifier groups a
  user's sessions — it is not authentication; access control beyond scoping (e.g.
  identity-aware proxy or rate limiting) is a deployment concern, not an application
  schema concern. User-scoped records are purged after the retention period (project
  lifetime in sandbox/dev; production defines timed retention).

## Versioning and rollback

Every deployment carries a git tag/commit-SHA version label, and each agent release
creates a **new versioned Agent Engine resource** (`<agent>-<git-sha>`) rather than
mutating a running one. Orchestration resolves agents through env-template pointers
(`AGENT_<NAME>_RESOURCE`); a release re-points its variable only after the new
resource passes the unit smoke test. The prior version's resource is retained (at
least N-1; older ones are removed by housekeeping once superseded). Consequences:

- rollback is a pointer switch back to the retained prior resource — no rebuild, no
  in-place mutation; the prior resource already has its matching staged prompt and
  locked shared-package dependency;
- multiple deployed versions coexist, satisfying the "prove agent versioning on
  multiple deployments" requirement with deployment history as evidence; and
- git tags map 1:1 to live or retained Agent Engine resources.

Prompt content is separately SHA-256 audited per agent run; the evaluation judge is
not a deployed agent.

## Local development

`deploy/docker-compose.yml` provides local PostgreSQL and GCS-compatible storage
substitutes. The `local-agents` profile runs local ADK adapters from
`deploy/compose/adapters/`; Agent Engine itself is not a Compose service. Vertex AI is
the only external dependency for the local stack.

## CI/CD (Azure DevOps)

Pipelines authenticate to GCP via a service-account key stored in Azure Pipeline secret
variables and deploy with a dedicated least-privilege GCP deployment service account;
no other long-lived credentials are stored in Azure variables. Images are pushed
to Google Artifact Registry.

There is one pipeline per deployable unit:
`pipelines/agents-{facilitator,business-reviewer,engineering-reviewer,synthesis}.yml` and
`pipelines/services-{story,artifact,report,orchestration}.yml`. Each uses the exact
unit/shared/deploy-manifest path filters documented in [repository-layout.md](repository-layout.md), runs unit
and contract checks, deploys only that unit to `dev`, then runs applicable smoke tests.
`pipelines/evaluation.yml` evaluates against `dev` on prompts, model configuration, or
agent code. A `judge.md`-only change runs evaluation only and never redeploys Agent
Engine. MCP discovery is runtime-based, so an MCP change does not redeploy agents, and
vice versa.

A normal unit pipeline is: test → build (Cloud Run units only) → deploy-dev → smoke.
Evaluation publishes results as pipeline artifacts. Production deployment remains an
optional manual-approved end-of-development action.

## Provisioning and operations

`deploy/bootstrap/bootstrap.sh` enables APIs and creates Cloud SQL, GCS, IAM, and the
Artifact Registry repository. The one-day sandbox procedure recreates the project,
updates identifiers, runs bootstrap, migrations, and the independent deploy scripts.

Health uses the FastAPI health endpoint and managed service checks. Monitoring uses
Cloud Monitoring and logging. Retention is decided in
[architecture.md](../design/architecture.md): everything is kept for the project
lifetime; no housekeeping runs in sandbox or dev (production defines timed retention).
