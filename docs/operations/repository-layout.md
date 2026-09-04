# Repository Layout

Monorepo structure, prompt management, shared packages, dataset location, and
deployment manifests. One repository (Azure DevOps) — each deployable unit has its own
directory, own pipeline, and own versioning, matching the de-coupled CI/CD decision in
`../decisions/tech-stack.md`.

## Structure

```
capstone_project/
├── docs/                        # this documentation set (index.md = reading order)
│
├── prompts/                     # prompts are static data, not code (tech-stack.md)
│   ├── facilitator.md
│   ├── business_reviewer.md
│   ├── engineering_reviewer.md
│   ├── synthesis.md
│   └── judge.md                 # evaluation judge prompt (evaluation-tests.md)
│
├── agents/                      # one directory per Agent Engine deployment
│   ├── facilitator/             #   agent code, agent config, requirements.txt
│   ├── business_reviewer/       #   (adk deploy agent_engine builds the container)
│   ├── engineering_reviewer/
│   └── synthesis/
│
├── mcp_servers/                 # one directory per Cloud Run MCP service
│   ├── story/                   #   server code + own Dockerfile
│   ├── artifact/
│   └── report/
│
├── orchestration/               # FastAPI entry service
│   ├── app/                     #   routes, session/turn state machine, gate logic
│   ├── clients/                 #   shared instrumented wrapper (Agent Engine + MCP)
│   └── Dockerfile
│
├── shared/                      # shared Pydantic schema package — single source of truth
│   └── review_schemas/          #   models from design/schemas.md
│                                #   (consumed by agents, MCP servers, orchestration, tests)
│
├── dataset/                     # mock backlog (mock-data.md)
│   ├── stories/*.json           #   story content + epic/roadmap context
│   └── expected/*.json          #   expected outcomes — never exposed to agents
│
├── tui/                         # terminal client (session ID holder, state machine)
│
├── tests/
│   ├── unit/                    #   gate logic, schema validation, wrappers
│   ├── contract/                #   MCP tool contract tests (schemas.md §7)
│   ├── integration/             #   session restore, artifact lineage, report flow
│   └── evaluation/              #   LLM-as-judge suite over dataset/ (evaluation-tests.md)
│
├── deploy/
│   ├── bootstrap/               #   gcloud scripts: APIs, Cloud SQL, GCS, IAM, Artifact Registry
│   ├── agents/                  #   per-agent `adk deploy agent_engine` scripts + env templates
│   ├── docker-compose.yml       #   local full-stack for evaluation runs
│   └── env/                     #   .env templates (identifiers only; no secrets committed)
│
├── pipelines/                   # Azure Pipelines definitions
│   ├── agents-*.yml             #   one per agent (independent deploy + smoke tests)
│   ├── services-*.yml           #   MCP servers + FastAPI (build, push, deploy-dev)
│   └── evaluation.yml           #   evaluation suite; triggered on prompt/model/agent change
│
└── pyproject.toml               # workspace metadata, tooling config (ruff, pytest)
```

## Prompts directory

- **Path & naming**: `prompts/<agent>.md` — one file per agent, filename = agent name;
  the judge prompt lives there too (`judge.md`). Loaded at startup from `PROMPTS_DIR`
  (defaults to `./prompts`); agents never inline prompts in code.
- **Versioning**: prompts are versioned in git like any source; the deployed agent
  version label (git tag/SHA) therefore also identifies the prompt version. Each
  `AgentRunRecord` additionally logs the prompt content hash, so a run is traceable to
  the exact prompt text even between tags.
- **Editing**: changing only a prompt file requires redeploying that one agent
  (independent pipeline) and triggers the evaluation pipeline (prompt change — see
  `../quality/evaluation-tests.md`).

## Shared packages

- `shared/review_schemas` — every model in `design/schemas.md`, imported by agents,
  MCP servers, orchestration, and tests. Contract changes here are breaking changes:
  bump the package version; contract tests fail loudly on drift.
- Consumed as a path dependency inside the monorepo (workspace install); publishing it
  to a registry is optional and deferred (Azure Artifacts decision in tech-stack.md).

## Dataset location

- `dataset/stories/*.json` — story content served by the story MCP server (JSON,
  Pydantic-validated, `StorySummary`/`StoryDetail` schemas).
- `dataset/expected/*.json` — expected outcomes, read **only** by the evaluation judge;
  the story server mounts `dataset/stories/` alone and has no path access to
  `dataset/expected/`.
- Dataset version = git commit; test results record the dataset version they ran
  against (mock-data.md).

## Deployment manifests

| Unit | Manifest location | Deployed via |
|---|---|---|
| Agents (×4) | `deploy/agents/<agent>/` (env template + script) | `adk deploy agent_engine` — ADK builds container from `agents/<agent>/` |
| Story / artifact / report MCP | `mcp_servers/<server>/Dockerfile` + `deploy/` env | Cloud Run from Artifact Registry image |
| FastAPI orchestration | `orchestration/Dockerfile` | Cloud Run from Artifact Registry image |
| Local evaluation stack | `deploy/docker-compose.yml` | docker compose (all services, mock backlog; only Vertex AI external) |

Rules: identifiers (project, region, service names, DB URL, bucket) only via
environment variables from `deploy/env/` templates; no secrets in the repository;
one pipeline per deployable unit in `pipelines/`.
