# Requirements Coverage

Traceability from every requirement in `../source/evaluation.md` to its design and
verification. Kept up to date as implementation proceeds; the audit table for the
automatic verification step and interviews.

## Design patterns

| Requirement | Covered by | Where designed | How verified |
|---|---|---|---|
| Pattern 1: sequential + loop agent + explicit invocation of separately deployed agents | Per-agent Agent Engine deployments invoked from the orchestration layer; facilitator dialogue loop | pattern-decisions.md, architecture.md (Deployment Model), data-flow.md flows 1–2 | evaluation tests (loop termination, loop cap); live demo |
| Pattern 2: sequential + parallel agent + loop agent | Parallel reviewer fan-out; reviews → synthesis → facilitator sequence; readiness loop | pattern-decisions.md, data-flow.md flow 1–2 | evaluation tests (reviewer correctness, delegation routing) |
| Pattern 3: LLM-driven delegation + user-in-the-loop + simple sequential agents in hierarchy | Facilitator DelegationDecision; PO dialogue; reviewer → synthesis chain invoked from the hierarchy | pattern-decisions.md, agents.md, data-flow.md flow 2 | evaluation tests (delegation routing, re-review synthesis) |

## Technical requirements

| Requirement | Covered by | Where designed | How verified |
|---|---|---|---|
| At least one MCP server in at least one agent | Story + artifact MCP servers attached to facilitator via `McpToolset` | tech-stack.md, mcp-servers.md, agents.md | contract/integration smoke tests |
| Deploy to Agent Engine | All four agents as separate Agent Engine deployments | architecture.md, deployment.md | deploy-dev pipeline stage |
| Full session management and persistence | ADK `DatabaseSessionService` on Cloud SQL; session lifecycle (active/parked/finalizing/completed); resume by client-held ID | architecture.md, data-flow.md flows 2–4 | integration tests (session restore); demo |
| Agent versioning on multiple deployments | Version labels = git tags/SHAs; independent per-agent redeployments; version-labeled logs | deployment.md, observability.md | deployment history + versioned runtime logs |
| Observability | Cloud Logging + Cloud Trace/OTel + metrics, correlation IDs, built-in Cloud Monitoring dashboards/alerts | observability.md | dashboards during tests/demo |
| Callbacks for chosen purpose | Before/after tool, after agent (decision validation), after model (length check), loop-iteration callback | observability.md | unit tests + logged events |
| Active conversation-length monitoring | Token/message count per facilitator session; warn 50%, act 75% (compaction/summary handover) | observability.md | unit test on counter + callback; eval tests |
| Session context usage | Synthesis deterministically appended to session context; lineage-scoped artifact references; facilitator evidence reads | data-flow.md flows 1–2, agents.md | integration tests |
| Simple MCP deployed to Cloud Run and integrated | Story server (read-only, mock backlog) on Cloud Run, Streamable HTTP | mcp-servers.md, deployment.md | contract tests; live demo |
| Agents evaluation tests implemented | LLM-as-judge suite over mock dataset; separate pipeline, gated on prompt/model/agent changes | quality/evaluation-tests.md, quality/mock-data.md | pipeline execution; results as artifacts |

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
| Separate viewpoints combined into a coherent final evaluation | Synthesis agent contract; two-latest-artifacts rule (agents.md) |
| Example interactions where a user resolves business/technical conflicts | conflicting + partial-resolution mock scenarios; dialogue loop (data-flow.md flow 2); live demo |
