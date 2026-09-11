# Capstone Project Documentation

Parallel Business & Engineering Review Team — multi-agent system evaluating user
stories from business and engineering perspectives in parallel, synthesizing the
findings, and resolving conflicts with the Product Owner in the loop.

## Reading order

1. **Source material** (given input)
   - [Topic](source/topic.md) — problem context and project task
   - [Evaluation](source/evaluation.md) — evaluation steps, design patterns, technical requirements
2. **Decisions**
   - [Pattern decisions](decisions/pattern-decisions.md) — workflow patterns and how they are fulfilled
   - [Tech stack](decisions/tech-stack.md) — technologies, environment, MCP strategy, CI/CD decisions
3. **Design**
   - [Architecture](design/architecture.md) — components, deployment model, session and state
   - [Data flow](design/data-flow.md) — flows between UI, orchestration, agents and MCP servers
   - [Agents](design/agents.md) — per-agent specifications and delegation schema
   - [API contract](design/api-contract.md) — FastAPI endpoints, status/error codes, idempotency, client interaction states
   - [Schemas](design/schemas.md) — shared Pydantic models, identifiers/lineage, audit records, error taxonomy, MCP field-level contracts
   - [MCP servers](design/mcp-servers.md) — server contracts
   - [Observability](design/observability.md) — telemetry, callbacks, retry and timeout policy
   - [Example interaction](design/example-interaction.md) — end-to-end conflict-resolution walkthrough of one story
4. **Quality**
   - [Evaluation tests](quality/evaluation-tests.md) — LLM-as-judge regression suite
   - [Mock data](quality/mock-data.md) — dataset, scenarios, expected outcomes
   - [Requirements coverage](quality/requirements-coverage.md) — traceability matrix
5. **Operations**
   - [Deployment](operations/deployment.md) — GCP layout, versioning, CI/CD pipelines
   - [Connectivity & identity](operations/connectivity-identity.md) — Cloud SQL access,
     IAM principals, MCP audience tokens, GCS signing, secrets
   - [Repository layout](operations/repository-layout.md) — repo structure, prompts directory, shared packages, dataset, manifests

## Local (home) development phase

Development on a private trial account is documented separately in
[../docs-local/](../docs-local/index.md): local decisions, phased development plan, and
runbook. Where the two sets differ, `docs/` describes the target/company setup.

## Conventions

- Diagrams: Mermaid inline; ASCII sequence diagrams generated from PlantUML sources in
  `design/diagrams/` (regenerate with `plantuml -ttxt <flow>.puml`).
- All schemas are strict Pydantic models defined authoritatively in
  [design/schemas.md](design/schemas.md); prompts live as static data in the repository,
  separate from code.
