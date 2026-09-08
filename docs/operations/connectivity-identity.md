# Connectivity, identity, and secrets

This document specifies how every runtime and deployment path reaches its dependencies,
which identity it uses, and where its secrets live. It complements
[deployment.md](deployment.md); resource names come from `deploy/**/.env.example`
templates and bootstrap outputs, never from this file.

## Identity model

| Principal | Used by | Grants |
|---|---|---|
| Deployment SA (`deployer@`) | Azure pipelines only | Create/update Cloud Run services, Agent Engine deployments, Artifact Registry writes, Cloud SQL schema migration runs (via `run-migrations.sh`), Secret Manager `secretAccessor` for deploy-time values. No runtime data access. |
| Orchestration runtime SA | FastAPI on Cloud Run | Agent Engine `aiplatform.user` (invoke all four agent deployments), `secretAccessor` for its own secrets, Cloud SQL IAM database login, `objectViewer` on the artifact bucket, `iam.serviceAccountTokenCreator` on itself (signed URLs, MCP audience tokens). |
| Facilitator runtime SA | Agent Engine facilitator deployment | Read-only MCP tool access (story, artifact), Cloud SQL IAM database login for its ADK `DatabaseSessionService` session, `secretAccessor` for its own config. No Agent Engine invocation rights, no artifact writes. |
| Reviewer/synthesis runtime SAs | Agent Engine execution-layer deployments | Stateless single-turn runs; `secretAccessor` for their own config only. No MCP tool access, no Cloud SQL login (no session state), no GCS access — inputs and outputs pass through orchestration. |
| MCP service runtime SAs | story / artifact / report on Cloud Run | Cloud SQL IAM login (artifact, report), `objectAdmin` scoped to the artifact bucket (artifact) or a report prefix (report). Story needs none beyond its own config secret. |

Each Cloud Run service and Agent Engine deployment is created with exactly one runtime
service account; the deployment SA attaches it at deploy time. Workload identity
federation for the pipeline (replacing the stored SA key) is the documented
production-promotion step, not part of the sandbox setup.

## Cloud SQL connectivity

- **Cloud Run (FastAPI, artifact, report)**: Unix socket via the Cloud Run
  service-agent connector (`/cloudsql/<instance>`). No public IP exposure for these
  services; the instance connection name comes from bootstrap via env template.
- **Agent Engine (facilitator)**: whether Agent Engine deployments can attach a
  network/VPC peering in this sandbox is **to be proven by the deployment spike
  below** — the design assumes private IP via a serverless VPC connector if supported.
  If not (the likely case in a fresh sandbox), the documented fallback is TLS over
  public IP restricted to Google service ranges where possible, still with IAM
  database authentication (no password secrets either way).

**Deployment spike (blocking prerequisite for the persistence design):** before
building the full service set, one scripted spike must prove the chain
*Agent Engine agent → authenticated Cloud Run MCP → Cloud SQL session persist →
restore*, recording the exact ingress setting, token audience, identities, and a
passing trace. If the sandbox makes any link impractical, simplify that link for the
capstone (e.g. public ingress with mandatory ID-token auth) rather than working
around it per service.
- **Migrations**: `deploy/cloud-sql/run-migrations.sh` runs from the pipeline runner
  (Cloud Build/VM) over private IP or temporary public IP with the deployment SA;
  migrations are ordered, forward-only SQL files.

### Connection pooling

| Service | Pool |
|---|---|
| FastAPI | `asyncpg` pool, `min 1 / max 5` per container; Cloud Run max concurrency 20 keeps one pool per instance sufficient |
| Artifact MCP | `min 1 / max 5` per container |
| Report MCP | `min 0 / max 2` (render path is rarely concurrent) |
| Facilitator (ADK session service) | connector-managed; one connection per active session turn |

Pool exhaustion is a retryable `UPSTREAM_UNAVAILABLE`; no service may open a connection
per request.

## Cloud Run → MCP service authentication

- All three MCP services deploy with `--no-allow-unauthenticated`; the intended
  `--ingress internal-and-cloud-load-balancing` must be confirmed by the spike — if
  Agent Engine's egress path is not admitted by internal ingress, the capstone
  fallback is default ingress with mandatory ID-token authentication (identity, not
  network position, is the security boundary in this design).
- Callers (FastAPI SDK client, facilitator `McpToolset`) attach an **ID token whose
  audience is the target service's URL** (or its configured custom audience), obtained
  via the metadata server (Cloud Run) or `google.auth` (Agent Engine). The caller's own
  runtime SA email is the token's *issuer identity*, not the audience. Audiences are
  per-service and injected from the env template, never hardcoded.
- The report MCP additionally rejects any caller whose authenticated principal is not
  the orchestration runtime SA (tool authorization table in
[../design/mcp-servers.md](../design/mcp-servers.md)).

## GCS access and signed URLs

- Artifact reads/writes use the owning service's SA via uniform bucket-level access;
  no ACLs, no keys.
- FastAPI issues expiring signed URLs (V4, 10-minute default) for report downloads.
  Signing uses the orchestration SA's credentials, which is why it holds
  `iam.serviceAccountTokenCreator` on **itself** — the commonly missed prerequisite for
  SA-based signing.
- Signed-URL generation failure is retryable (`UPSTREAM_UNAVAILABLE`) per the
  finalization retry policy in [../design/observability.md](../design/observability.md).

## Secret storage

- All runtime secrets (DB connection identifiers, bucket name, MCP endpoints and
  audiences, Agent Engine resource IDs, the story server's Azure DevOps PAT)
  live in Secret Manager, one secret per service, mounted via env-template
  indirection at deploy time. The Azure PAT is only mounted on the story MCP
  service in production (`azure` source); its egress path is `dev.azure.com`.
- Deployment values the pipeline needs (GCP project, region, SA emails) are non-secret
  pipeline variables; only the deployment SA key is a secret variable, replaced by
  workload identity federation on production promotion.
- Nothing in this document or the repo contains instance names, bucket names, or SA
  emails as literals.
