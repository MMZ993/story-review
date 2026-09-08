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
| Hidden-conflict story | both reviews individually positive, but their justifications rest on contradictory assumptions — synthesis flags the cross-perspective conflict, PO resolves via dialogue |
| Comments-benign story | clean story plus a benign resolved comment thread — comments must not create findings; arc identical to clean (comment-invariance) |
| Comments-clarify-business story | description ambiguous for both perspectives; comments resolve the business side only — business review positive via comments, engineering findings drive an engineering-weak arc |
| Comments-complete-engineering story | engineering-thin description; comments carry the missing engineering policy — both reviews positive (comment-completion) |

The three comment scenarios are **t1-only** content variants (dataset
extension, not part of the cross-template matrix): each has exactly one
story, in T1, and its own scenario-canonical expected file with
`applies_across_templates: false`.

## Expected-file contract (`dataset/expected/<scenario>.json`)

Each scenario has **one canonical expected file** (not one per case). The
dataset loader (`dataset/loader/`) expands each scenario file to the
per-template test cases of that scenario — format invariance across templates
is thereby enforced structurally, and `story_id` lives on the expanded case,
not in the file. Each file is the versioned dialogue script and
expected-transition specification that drives integration tests and the
deterministic assertions in
[evaluation-tests.md](evaluation-tests.md). It contains:

- `scenario` and dataset schema version;
- `po_script`: an ordered list of PO turns — each turn is exactly one of
  `message` (Text) or `po_accepted: true`, mirroring the `TurnRequest` contract
  (`schemas.md`: exactly one of message or acceptance, never both);
- `expected_turns`: one entry per PO turn with the expected
  `DelegationDecision` (invoke / reuse_previous / open_issues), expected
  `outcome` (`continue` / `park` / `finalize`), expected session `state`, the
  perspective(s) of any artifacts produced that turn, and expected
  `turn_number`;
- `expected_findings`: per-perspective **semantic stubs** (`max_severity`,
  `required` finding keys with `min_severity`/topic/turn placement) — runtime
  finding IDs are never pinned;
- `expected_conflicts`: required conflict references per turn;
- `expected_final`: final session state, `final_turn_number`,
  `facilitator_turn_count`, `finalized-review` contents (acceptance flag,
  remaining issues), and requested report formats;
- `invariance`: whether the expectation applies across all templates of the
  scenario and the allowed deviation (e.g. info-level formatting notes only).

The PO script is executed verbatim by the test runner; nothing in it is generated
or adaptive. A mismatch between any expected turn and the observed turn fails the
case before the judge is invoked. Expected files live only in
`dataset/expected/`, are excluded from every runtime image (see
[repository-layout.md](../operations/repository-layout.md)), and are versioned in git
with the dataset.

## Rules

- Expected outputs live with the dataset, never in agent prompts or code.
- Story MCP server returns stories and backlog data in **JSON format** (strict schema,
  Pydantic-validated).
- Dataset versioned in git; test results tied to dataset version.
- Same stories used in the live demo — what evaluators see is what the tests verify.
