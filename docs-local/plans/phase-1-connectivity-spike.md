# Phase 1 connectivity spike plan

This plan proves the minimum Agent Engine-to-Cloud-SQL connectivity chain before production application units are built.

## Objective and decision

Prove, with one disposable agent and one disposable MCP service, this chain:

```text
Agent Engine (sa-facilitator)
  -> authenticated HTTPS request with an ID token
Cloud Run connectivity MCP (sa-artifact-mcp)
  -> Cloud SQL connector over /cloudsql/<instance-connection-name>
PostgreSQL
  -> create session marker -> retrieve the same marker in a fresh request
```

The agent invokes one MCP tool twice: `persist_session` stores a generated
marker under a supplied session ID, then `restore_session` returns it. The run
passes only when the restored marker and session ID exactly match the stored
values, and Cloud Logging shows the agent call and service request under the
same test correlation ID.

The result decides the home-phase connectivity posture:

| Outcome | Decision |
|---|---|
| Agent Engine reaches Cloud Run with `internal-and-cloud-load-balancing` ingress and the Cloud Run MCP reaches Cloud SQL | Retain this ingress setting. Investigate private-IP/VPC only if Agent Engine networking is supported and its added cost is justified. |
| Agent Engine cannot reach the service through internal ingress, but the ID-token-authenticated call succeeds with default ingress | Use default ingress plus mandatory ID-token authentication for the home phase, as allowed by `docs/operations/connectivity-identity.md`. |
| The Cloud Run connector cannot use the existing instance, or Agent Engine cannot authenticate as the intended runtime SA | Stop after recording the failed link. Do not add per-service workarounds; decide a documented simplification with the owner before continuing. |

This spike does not implement any reviewer, facilitator, production MCP
contract, shared schema, orchestration endpoint, or permanent application
deployment.

## Preconditions

- Phase 0 remains healthy: Terraform reports no drift; the existing Artifact
  Registry, Cloud SQL instance, and runtime service accounts exist.
- The owner approves each billed write action after reviewing its Terraform plan
  or deployment command. Cloud Run and Agent Engine deployments may consume
  trial credits; Cloud Run stays at zero minimum instances.
- The executor has ADC and sources `infra/envs/home.env`. Identifiers remain in
  that ignored file and Terraform outputs; no identifier or credential is
  committed to this plan.
- The existing `sa-facilitator` and `sa-artifact-mcp` identities are used. The
  former is the Agent Engine runtime identity and caller; the latter is the
  Cloud Run runtime identity and has the existing Cloud SQL instance-user grant.

## Proposed disposable layout

Keep spike-only code separate from the canonical production paths until the
connectivity decision is known:

```text
spikes/connectivity/
├── agent/                  # minimal ADK agent and locked requirements
├── mcp/                    # minimal MCP HTTP server, Dockerfile, locked requirements
├── sql/001_session_marker.sql
├── tests/                  # deterministic unit and service-contract tests
├── deploy-agent.sh         # stages and deploys the disposable Agent Engine resource
├── deploy-mcp.sh           # builds/pushes image; Terraform owns the Cloud Run service
└── README.md                # local invocation and correlation-ID procedure
infra/modules/connectivity-spike/
├── main.tf                 # Cloud Run service, runtime SA attachment, Cloud SQL connector
├── variables.tf
└── outputs.tf
```

The Terraform module owns the disposable Cloud Run service, its service-account
attachment, Cloud SQL instance connection configuration, `roles/run.invoker`
for `sa-facilitator`, and service configuration. The Agent Engine resource is
created by `spikes/connectivity/deploy-agent.sh`, consistent with D2. The
module accepts an image reference produced by the build script; the initial
Terraform plan is reviewed only after that immutable image reference is known.

No public unauthenticated endpoint is permitted. The initial Cloud Run service
uses `--no-allow-unauthenticated` equivalent IAM configuration and
`internal-and-cloud-load-balancing` ingress. Its invocation audience is the
service URL returned by Terraform, injected into the agent deployment
configuration rather than hardcoded.

## Implementation increments

### 1. Confirm interfaces and write tests

Before implementation, confirm the installed ADK and MCP library versions and
the supported Agent Engine deployment mechanism for assigning a runtime service
account. Record the exact CLI/API form in Runbook 06.

Write and run failing deterministic tests before production-facing code:

- `persist_session` rejects an empty session ID or marker and records a marker
  once for a valid request.
- `restore_session` returns the stored marker for a valid session ID and a
  defined not-found response for an unknown ID.
- The service contract requires an authenticated caller; the local test adapter
  supplies a fake verified principal rather than disabling the authorization
  boundary in deployed code.
- The agent invocation carries a caller-generated correlation ID to the MCP
  request and exposes the tool result without interpretation.

Use a small PostgreSQL test fixture where declared tooling supports it. The
Cloud SQL proof is an integration/deployment check, not a unit-test substitute.

### 2. Add database migration and least-privilege database access

Add the ordered SQL migration creating only a session-marker table, with a
primary-key session ID, marker value, creation time, and correlation ID. Add
only the database user/grants necessary for `sa-artifact-mcp` to create and read
those rows through IAM database authentication.

Before applying the migration, document the exact non-destructive migration
command and rollback limitation (forward-only schema). Verify the migration by
connecting through the same Cloud Run connector path used by the service; do
not use a password or a local direct-public-IP shortcut.

### 3. Build and provision the Cloud Run MCP service

Create the minimal MCP HTTP service and its Docker image. It exposes exactly
`persist_session` and `restore_session`, returns structured JSON, logs the
correlation ID, and has a `/healthz` endpoint. It does not use GCS, Secret
Manager values, shared review schemas, or production datasets.

Add the Terraform module and root wiring. The service must:

- run in `europe-west4` as `sa-artifact-mcp`;
- attach the existing Cloud SQL instance using its Terraform output and Unix
  socket path;
- have min instances 0 and a bounded concurrency/timeout suitable for this
  single-request spike;
- initially use `internal-and-cloud-load-balancing` ingress;
- deny anonymous invocation and grant `roles/run.invoker` only to
  `sa-facilitator`;
- emit the service URL and configured audience as outputs for the agent deploy
  script.

Run `terraform fmt -check -recursive`, `terraform validate`, and a saved
`terraform plan` first. The owner reviews the exact plan before approval to
apply. Verify the deployed service configuration, runtime identity, ingress,
Cloud SQL attachment, and invoker policy with read-only `gcloud` commands.

### 4. Deploy and prove the Agent Engine caller

Implement the smallest ADK agent that obtains an ID token through supported
Google authentication libraries using its runtime credentials, with the Cloud
Run service URL as audience. Deploy it as a clearly disposable, versioned
Agent Engine resource using `sa-facilitator`; record the exact resource name
only in the ignored local evidence or command output, not Git.

First invoke `persist_session`, then invoke `restore_session` in a new agent
request with the same session ID and correlation ID. Capture:

- agent deployment runtime service account;
- Cloud Run ingress setting, service URL/audience form, runtime service account,
  and invoker IAM principal;
- Cloud SQL connector configuration and IAM database identity;
- the two tool responses, with IDs/markers redacted as appropriate;
- Cloud Logging request entries and Agent Engine logs/traces tied by correlation
  ID; and
- the exact test command, timestamps, and pass/fail result.

### 5. Apply the decision gate and clean up

If internal ingress is rejected from Agent Engine, change only the ingress
setting to default ingress, retain required ID-token authentication and the
least-privilege invoker binding, re-plan/review/apply, and rerun the same test.
Record this as the approved fallback in `docs-local/local-decisions.md` and
Runbook 06.

Do not provision VPC peering, a Serverless VPC Access connector, or other
network resources during the first pass. Propose their incremental cost and a
separate plan only if the primary/fallback test cannot meet the objective.

After evidence is recorded and accepted, the owner personally removes the
throwaway Agent Engine resource and Cloud Run Terraform resource. Preserve the
source, migration, plan summaries, sanitized traces, and final connectivity
decision in Runbook 06; do not retain live throwaway services.

## Verification and evidence checklist

Runbook 06 must include, in execution order:

1. dependency/version and Agent Engine runtime-SA support confirmation;
2. failing-then-passing unit/contract test evidence;
3. Terraform formatting, validation, reviewed plan, and apply summary;
4. migration command/result and database IAM grant verification;
5. Cloud Run configuration and IAM verification;
6. Agent Engine deployment and end-to-end two-request trace; and
7. the ingress/connectivity decision, cost observed, and teardown evidence.

The Phase 1 exit criterion is met only by a passing end-to-end chain or an
owner-approved, documented fallback. A Cloud Run-only database smoke test, an
unauthenticated endpoint, or a direct local database connection is insufficient.

## References

- `docs/operations/connectivity-identity.md` — authoritative identity and
  connectivity model; defines this blocking spike and permitted ingress fallback.
- `docs/operations/deployment.md` — deployment ownership and regional model.
- `docs-local/local-decisions.md` D2, D4, and D5 — Terraform/app deployment
  split, local-first loop, and trial-cost constraints.
- `docs-local/runbooks/04-resource-skeletons.md` — current Cloud SQL public-IP
  fallback and the deferred private-connectivity decision.
