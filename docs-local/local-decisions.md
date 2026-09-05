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

## Differences from `docs/` (summary)

| Topic | `docs/` (company) | Home phase |
|---|---|---|
| Project lifetime | one-day sandbox, daily recreation | static trial project |
| CI/CD | 8 Azure unit pipelines + evaluation | local scripts + runbook; pipelines at promotion |
| Pipeline auth | SA key in Azure secrets (WIF at production) | ADC / `gcloud auth application-default login` |
| Retention/housekeeping | project lifetime, no cleanup | manual pruning per D5 |
