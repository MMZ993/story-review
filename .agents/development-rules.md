# Development rules — application code

Load this file when a session involves writing or changing application code
(Python, schemas, tests, agents, MCP servers, orchestration, TUI). Linked from
AGENTS.md. Derived from the pi-config development skills, adapted to this project.

## Understand before editing

- Inspect the target file and its surrounding context before editing; read the
  complete file unless too large, then the relevant sections with context.
- Check callers, references, and interface contracts before changing behavior.
- The authoritative contracts are `docs/design/schemas.md` and the other design
  docs — implementation follows them; deviations are design changes, not tweaks.

## Conventions

- Reuse established project patterns, naming, and error-handling style; verify a
  dependency is declared before relying on it.
- Python tooling: `uv`; per-unit `requirements.lock` via `uv pip compile`.
- Strict Pydantic models everywhere a payload crosses a boundary; no free-form
  prose parsed programmatically (per docs/design/schemas.md).
- Static data (prompts, schemas, config) separate from executable logic.

## Documentation-first

- Write the docstring/documentation comment before implementing every function,
  class, and module: purpose, inputs, outputs, side effects, errors, constraints.
- Keep it aligned with behavior; no comments restating syntax.

## Test-first

- Write one behavior-oriented failing test before the implementation; confirm it
  fails for the right reason.
- Test observable behavior, not implementation details; descriptive names;
  independent, deterministic, fast; no placeholder/skipped tests.
- For genuinely untestable changes (docs, config), state why a test does not apply.
- Shared schemas (`shared/review_schemas`) always get unit tests for validators.

## Design and maintainability

- Small focused files; split when a file exceeds one cohesive responsibility.
  Guideline: prefer < ~300 lines per module; split earlier if it does two jobs.
- One purpose per function/class; extract separately testable behavior instead of
  accumulating branches.
- Code reads like a book: extract logically grouped operations into small,
  intention-revealing helpers so the calling code reads as a description of
  *what* happens (e.g. `retryable = is_retryable(error)` or
  `ensure_perspective_matches_type(reference)`), with the helpers explaining
  *how*. Not one helper per line — but whenever a block of 2+ lines forms one
  logical step, name it. Reader-first: a maintainer should follow the intent
  without mentally simulating the implementation.
- Side effects (I/O, framework calls) at module boundaries; core decision logic
  deterministic where practical.
- Least complex adequate design; duplication acceptable over obscuring
  abstraction; no speculative refactors or unrelated cleanup.
- Validate at module boundaries; never let invalid state flow deeper.

## Verification (before declaring a change done)

- Match verification to risk: trivial (docs/config) → inspect diff + format check;
  focused code → focused test + lint/type; significant/cross-cutting → broader
  suite.
- Use only the project's declared commands (Makefile / pyproject); do not invent.
- For infrastructure-adjacent code see infra-rules.md; never apply infra as
  verification.
- Load and follow the `verify` skill when wrapping up a code change.

## Debugging

- No speculative symptom fixes: reproduce minimally, read full errors, trace to
  source, state the root cause and smallest fix before editing.
- Stop and report evidence when the root cause cannot be identified.

## Independent review

- Request a read-only review (via the `request-review` skill / subagent) for:
  schema changes, gate/orchestration logic changes, security-relevant behavior,
  multi-file non-obvious logic, or when the owner asks. Skip for docs, formatting,
  and trivial config.
