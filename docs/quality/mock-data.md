# Mock Data

## Purpose

Single dataset reused for two purposes: **live demo/presentation** and
**regression/integration tests** (see [evaluation-tests.md](evaluation-tests.md)). The project is a capstone,
not a production system — but designed so it could be promoted, so mock data mirrors a
real backlog's shape.

## Structure

- **Backlog store** (mock data store behind the story MCP server): a set of user stories
  with varied quality.
- Each story carries:
  - story content (title, description, acceptance criteria),
  - epic/roadmap context,
  - **expected outcomes** (not exposed to the agents): known business gaps, technical
    risks, expected conflicts, expected clarification path, expected readiness result.

## Scenario coverage

| Story type | Purpose |
|---|---|
| Clean story | happy path — both reviews positive, story reaches `ready` quickly |
| Business-weak story | business gaps found, technical side solid |
| Engineering-weak story | missing edge cases/dependencies, business side solid |
| Conflicting story | business and engineering findings contradict — synthesis flags conflicts, PO resolves via dialogue |
| Partial-resolution story | PO clarification resolves one side only — re-review of one perspective, new conflict on the other side emerges |
| Unresolvable story | hits loop safety cap — facilitator parks the story |

## Rules

- Expected outputs live with the dataset, never in agent prompts or code.
- Story MCP server returns stories and backlog data in **JSON format** (strict schema,
  Pydantic-validated).
- Dataset versioned in git; test results tied to dataset version.
- Same stories used in the live demo — what evaluators see is what the tests verify.
