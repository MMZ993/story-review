# Evaluation Tests

## Purpose

Agent evaluation tests implemented as **regression/integration tests judged by an LLM**:
real agents, real prompts, real MCP servers — no mocks of the agents themselves.

## Approach: LLM-as-judge over mock scenarios

- Test cases are stories from the **mock dataset** (see [mock-data.md](mock-data.md)) with known
  expected outcomes (conflicting reviews, gaps, clarification paths).
- The full flow runs against the real deployed (or locally running) agents. Persistence
  cases never read a later story run: they restore and continue the original run, then
  assert cross-run artifact reads are rejected.
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
| Artifact persistence | save reviews, restore the session, and issue later requests in the **same story run**; verify same-run lineage reads and immutable versions |

## Deterministic assertions

The runner evaluates deterministic requirements before invoking a judge. Each case
specifies its required assertions in `dataset/expected/<case>.json`. Applicable failures
fail the case immediately:

- expected business/engineering finding IDs and required conflict references exist;
- initial reviewer spans overlap within the request/turn trace (parallel fan-out from
  orchestration);
- every delegated reviewer/synthesis call has FastAPI orchestration as caller;
- selected reviewer routing exactly matches the scripted PO clarification;
- synthesis inputs are the caller-selected maximum versions from one story run;
- artifact reads reject another run and restore succeeds in the original run;
- gate outcome, turn cap, requested report formats, and final session state match; and
- the `finalized-review` artifact contains the latest synthesis, dialogue resolutions,
  remaining issues, and explicit acceptance state used by every rendered report.

## Judge design and pass policy

The judge is a plain stateless Vertex AI call, not another deployed agent. Configuration
is versioned in `tests/evaluation/config.yaml`: model `gemini-2.5-pro`, temperature `0`,
one candidate, and `prompts/judge.md` identified by SHA-256. The run records the returned
publisher model/version metadata with that configuration.

For every case that passes deterministic assertions, one judge call receives the
captured typed outputs plus expected outcomes. `JudgeResult` in `../design/schemas.md`
scores five dimensions from 0 to 4: review coverage, grounding, conflict resolution,
delegation, and final-state quality. A case passes only when every dimension is at least
3, the arithmetic mean is at least 3.5, and no judge issue has `blocker` severity.

A transient transport failure permits one retry with identical input (two total
attempts). Invalid structured output or a second transport failure fails the case; it is
not replaced with another sample. Best-of-N, majority voting, and selecting the highest
score are prohibited. Every required dataset case must pass; one failed deterministic
assertion or judge result makes `evaluation.yml` exit non-zero. Aggregate scores are
reported for trend analysis but never override a failed case.

## Execution modes

1. **Local (preferred)**: docker compose starts FastAPI, MCP services, PostgreSQL and
   GCS-compatible substitutes, plus local ADK adapters for the four agents. It does not
   run Agent Engine. The suite uses the mock backlog and saves output; only Vertex AI is
   external.
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
- Judge policy is fixed: one result per case, at most one transport retry, no best-of-N,
  and all required cases must pass for the pipeline gate.
- Results logged with the observability correlation structure — a failed case traces to
  the exact agent turns (see [observability.md](../design/observability.md)); test outputs saved as pipeline
  artifacts.
