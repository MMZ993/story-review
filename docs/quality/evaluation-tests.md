# Evaluation Tests

## Purpose

Agent evaluation tests implemented as **regression/integration tests judged by an LLM**:
real agents, real prompts, real MCP servers — no mocks of the agents themselves.

## Approach: LLM-as-judge over mock scenarios

- Test cases are stories from the **mock dataset** (see `mock-data.md`) with known
  expected outcomes (conflicting reviews, gaps, clarification paths).
- The full flow runs against the real deployed (or locally running) agents.
- A separate **judge LLM** — different prompt, no shared state with the agents —
  evaluates whether each step behaved correctly (review quality, conflict detection,
  delegation routing, loop behavior, final readiness decision). See Judge design below.

## What is tested

| Aspect | Scenario type |
|---|---|
| Reviewer correctness | story with known business gaps / technical risks — reviewers must find them |
| Conflict detection | story producing deliberately conflicting business/engineering findings — synthesis must flag them |
| Delegation routing | PO clarification resolving only one side — facilitator must invoke only the affected reviewer, with correct extra context |
| Re-review synthesis | after single-perspective re-review — synthesis must use latest artifact per perspective and detect newly introduced conflicts |
| Loop termination | story fully resolved — facilitator must reach `ready` within the loop cap |
| Loop safety cap | unresolvable story — facilitator must park the story at max iterations instead of looping forever |
| Artifact persistence | reviews reachable as permanent artifacts in later story runs |

## Judge design

- A **single-run judge agent** (or plain LLM calls — same thing without agent
  scaffolding; decided at implementation) with its own prompt, no shared state with the
  system under test.
- Input per case: what we got (e.g. synthesis result, conflict resolution, delegation
  decision, final output) + expected outcome from the mock dataset (e.g. "conflict must
  be caught", required points to meet).
- Structured (Pydantic) output per case:
  - `passed` (true/false),
  - `issues` — what exactly was wrong,
  - `comment` — free-text justification,
  - `score` — numeric value (LLM-subjective, but consistent enough to compare runs).

## Execution modes

1. **Local (preferred)**: docker compose brings up the whole stack (agents, MCP servers,
   FastAPI, mock backlog) — extra Dockerfiles where needed — runs the test suite and
   saves output. Only Vertex AI is external.
2. **In-pipeline**: same compose stack on the Azure runner — possible only if the runner
   can reach Vertex AI (network/auth to be verified).
3. **Post-deployment vs dev**: if the runner cannot reach Vertex AI, integration tests
   run against the deployed dev environment instead.
4. **Standalone**: the integration/evaluation suite can be run on demand against dev,
   independent of the deploy pipeline.

## CI integration

- Pipeline stages: `pytest` (unit/contract) → `build` → `deploy dev` → `integration /
  evaluation tests vs dev` → `deploy prod` (deferred, optional).
- Trigger policy per observability decision: full evaluation only on prompt/model/agent
  changes; unit and contract tests on every pipeline run.
- Non-determinism handling: judge runs per case; flakes mitigated by explicit pass
  criteria and, if needed, best-of-N judging.
- Results logged with the observability correlation structure — a failed case traces to
  the exact agent turns (see `observability.md`); test outputs saved as pipeline
  artifacts.
