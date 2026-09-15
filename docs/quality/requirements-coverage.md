# Requirements Coverage

Traceability from every requirement in `../source/evaluation.md` to its design and
verification. Kept up to date as implementation proceeds; the audit table for the
automatic verification step and interviews.

## Status and evidence convention

Every row is currently in **designed** status: the design documents are complete and
the "How verified" column describes the *planned* verification, not an executed one.
As implementation proceeds each row moves through **implemented** (code/manifests
exist at the cited paths) to **verified** (the cited check has run and passed). A row
reaches verified only with evidence recorded inline: the pipeline run URL or
`correlation_id`/trace of the passing check, and the artifact location (test output,
log query, deployment history entry). Until then, no row claims executed verification.

## Design patterns

| Requirement | Covered by | Where designed | How verified |
|---|---|---|---|
| Pattern 1: sequential + loop agent + explicit invocation of separately deployed agents | Per-agent Agent Engine deployments invoked from the orchestration layer (Agent Engine client SDK); facilitator dialogue loop | pattern-decisions.md, architecture.md (Deployment Model), data-flow.md flows 1–2 | evaluation tests (caller assertion: orchestration invokes agents; distinct deployment-resource assertion per invocation; loop termination, loop cap); live demo |
| Pattern 2: sequential + parallel agent + loop agent | Parallel reviewer fan-out; reviews → synthesis → facilitator sequence; readiness loop | pattern-decisions.md, data-flow.md flow 1–2 | evaluation tests (overlapping reviewer spans; reviewer → synthesis call order; reviewer correctness, delegation routing) |
| Pattern 3: LLM-driven delegation + user-in-the-loop + simple sequential agents in hierarchy | Facilitator DelegationDecision; PO dialogue; reviewer → synthesis chain invoked from the hierarchy | pattern-decisions.md, agents.md, data-flow.md flow 2 | evaluation tests (delegation routing, re-review synthesis) |

## Technical requirements

| Requirement | Covered by | Where designed | How verified |
|---|---|---|---|
| At least one MCP server in at least one agent | Story + artifact MCP servers attached to facilitator via `McpToolset` | tech-stack.md, mcp-servers.md, agents.md | **verified** — live facilitator-initiated MCP tool call (`get_story`) from Agent Engine against the Cloud Run story server over the public domain, paired `tool_call` telemetry in Cloud Logging (Runbook 14 §D27 open item closed); agent-kit unit tests; MCP smoke tests |
| Deploy to Agent Engine | All four agents as separate Agent Engine deployments | architecture.md, deployment.md | **verified** — four engines deployed via deploy scripts, per-engine smoke PASS; Cloud Run → Agent Engine leg live (`:streamQuery?alt=sse`, one AE session per review session) — Runbook 14 increments 3–4 + increment-6 close |
| Full session management and persistence | ADK `DatabaseSessionService` on Cloud SQL; session lifecycle (active/parked/finalizing/completed); resume by client-held ID | architecture.md, schemas.md, data-flow.md flows 1–4 | integration tests (state transitions, session restore); demo |
| Agent versioning on multiple deployments | Version labels = git tags/SHAs; independent per-agent redeployments; version-labeled logs | deployment.md, observability.md | **verified** — per-agent versioned engines (deploy-label resource names), version labels carried into orchestration audit fields; independent redeploy + re-point proven live; **rollback proof live**: pointer re-point back to the previous engine + revision redeploy served a live flow-1 turn on each of forward/rollback/forward (Runbook 14 §Increment 7) |
| Observability | Cloud Logging + Cloud Trace/OTel + metrics, correlation IDs, built-in Cloud Monitoring dashboards/alerts | observability.md | **implemented** — structured JSON request logs with correlation IDs live on both Cloud Run services; log-based metrics + dashboard + the two alert policies applied and counting (Runbook 14 increment 6); Cloud Trace/OTel traces still planned |
| Callbacks for chosen purpose | ADK before/after tool and model plus after-agent validation; FastAPI emits the loop-iteration application event | observability.md | **verified** — telemetry unit tests (agent-kit) and live paired before/after `tool_call` events + model latency/token events observed from Agent Engine; `gate_decision`/`session_parked` FastAPI app events live (Runbook 14 increment-6 close + §D27 open item closed) |
| Active conversation-length monitoring | Model-tokenizer count; warn at 50%; at 75% validate a typed summary that preserves unresolved issues, decisions, lineage, and artifact references | observability.md | **implemented** — agent-kit unit tests for thresholds, typed-summary validation, checkpoint re-summarization, and safe-failure paths (context kept on any failure); D28 75% compaction callback shipped live on the facilitator engine (live trigger impractical: 10-turn cap vs 1M-token limit — recorded D28, Runbook 14 §Increment 7) |
| Session context usage | Synthesis deterministically appended to session context; lineage-scoped artifact references; facilitator evidence reads | data-flow.md flows 1–2, agents.md | integration tests |
| Simple MCP deployed to Cloud Run and integrated | Story server (read-only, mock backlog) on Cloud Run, Streamable HTTP | mcp-servers.md, deployment.md | contract tests; live demo |
| Agents evaluation tests implemented | Deterministic assertions plus fixed-threshold LLM judge; separate all-cases-pass pipeline gate on prompt/model/agent changes | quality/evaluation-tests.md, quality/mock-data.md, design/schemas.md | non-zero pipeline failure; typed results and traces as artifacts |

## Evaluation steps readiness

| Step | Preparation |
|---|---|
| Automatic verification of technical criteria | this table + implementation; CI stages produce the evidence (deployments, versioned logs, test artifacts) |
| Expert interviews (per-role scope) | agents.md (AI Engineer), data-flow.md + pattern-decisions.md (AI Workflow Designer), deployment.md + observability.md (AI DevOps) |
| Live demo | mock dataset scenarios (quality/mock-data.md); session restore; final report download |
| Explain every part of the implementation | docs set: decisions → design → quality → operations |

## Topic expected results

| Expected result | Covered by |
|---|---|
| Defined roles; parallel reviews expose more issues earlier | agents.md; data-flow.md flow 1 |
| Separate viewpoints combined into a coherent final evaluation | Synthesis contract and two-latest-artifacts rule (agents.md), followed by the deterministic `finalized-review` artifact incorporating dialogue resolutions and acceptance |
| Example interactions where a user resolves business/technical conflicts | [example-interaction.md](../design/example-interaction.md) end-to-end walkthrough; conflicting + partial-resolution mock scenarios; dialogue loop (data-flow.md flow 2); live demo |
