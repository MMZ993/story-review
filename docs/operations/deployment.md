# Deployment

## Google Cloud layout

| Resource | Service | Notes |
|---|---|---|
| FastAPI orchestration | Cloud Run | entry service, service-account ingress or authenticated demo route |
| Facilitator agent | Agent Engine | separate deployment, version-labeled |
| Business Reviewer | Agent Engine | separate deployment, version-labeled |
| Engineering Reviewer | Agent Engine | separate deployment, version-labeled |
| Synthesis & Conflict Resolver | Agent Engine | separate deployment, version-labeled |
| Story MCP server | Cloud Run | simple MCP |
| Artifact MCP server | Cloud Run | |
| Report MCP server | Cloud Run | |
| Session store | Cloud SQL (PostgreSQL) | ADK `DatabaseSessionService` |
| Artifacts | GCS bucket | `GcsArtifactService`, report files |

- Region: `europe-west4` (single region; no HA required for the capstone).
- All identifiers via environment variables; no secrets in code.
- Agents deployed with `adk deploy agent_engine` (ADK builds the container from source +
  `requirements.txt`); MCP servers and FastAPI from own Dockerfiles.

## Versioning

- Every deployment carries a version label = git tag/commit SHA.
- Agent versioning evidence: multiple sequential deployments per agent with distinct
  versions; runtime evidence via version-labeled logs/metrics (see observability.md).
- Rollback = redeploy the previous tag.

## CI/CD (Azure DevOps)

- Repo and pipelines in Azure DevOps; images pushed to **Google Artifact Registry**
  (pipeline authenticates to GCP via service-account key in Azure Pipeline secret
  variables).
- **De-coupled pipelines**: agents and MCP/FastAPI services deploy independently — MCP
  tools are discovered at runtime, so neither side requires redeploying the other. Each
  pipeline ends with contract/integration smoke tests against the dev environment.
  Optional combined run via pipeline trigger/checkbox.

### Pipeline stages

1. `pytest` — unit and contract tests (every run).
2. `build` — build and push MCP/FastAPI images to Artifact Registry, tagged with build
   number.
3. `deploy-dev` — Cloud Run + Agent Engine deployments (also produces versioning
   evidence).
4. `integration/evaluation vs dev` — full agent evaluation on prompt/model/agent-code
   changes (see `../quality/evaluation-tests.md`); otherwise smoke tests only. Outputs
   published as pipeline artifacts.
5. `deploy-prod` — optional, manual approval; only after end-of-development.

## Provisioning

- GCP resources provisioned via `gcloud` scripts (or Terraform if time permits) — one
  bootstrap script for the capstone project: enabled APIs, Cloud SQL instance, GCS
  bucket, service accounts + IAM, Artifact Registry repository.
- Work sandbox: 1-day project; daily procedure recreates the project and re-runs
  bootstrap + redeploys (env-var driven, no code changes).

## Operational procedures

- **Health**: FastAPI health endpoint; Cloud Run and Agent Engine built-in checks.
- **Monitoring**: built-in Cloud Monitoring dashboards and alert policies — no custom
  dashboard applications (see observability.md).
- **Session housekeeping**: separate process for retention of old sessions (all vs
  last X) — to be decided.
