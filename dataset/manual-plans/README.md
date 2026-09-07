# Manual test plans — per scenario (canonical cases)

Human-readable test plans for the story-review dialogue flow. Each plan
describes, for one scenario: the PO script (verbatim messages / acceptance),
the expected facilitator behavior per turn (`DelegationDecision`, outcome,
session state), the expected findings, and the expected final state.

These plans are the **authoring source** for the automated expected files
(`dataset/expected/<case>.json`, per `docs/quality/mock-data.md`); the
transcription is mechanical because the plans use the same vocabulary
(`schemas.md`: DelegationDecision, TurnOutcome, SessionState).

## Format invariance (the system requirement under test)

A plan belongs to the **scenario**, not to a work-item ID. The current T1
instance is listed per scenario; when the T2–T6 renderings exist
(`dataset/story-templates.md`), each rendering of the same scenario must pass
**this same plan** — same findings (semantic), same decisions, same readiness.
Formatting differences may produce at most info-level reviewer notes.

## Scenario → current story instance (T1 baseline column)

| Plan | Scenario | T1 story id | Title |
|---|---|---|---|
| `clean.md` | Clean | 5 | Invoice PDF in order confirmation email |
| `business-weak.md` | Business-weak | 10 | Google Pay at checkout |
| `engineering-weak.md` | Engineering-weak | 14 | Automatic payment retry on PSP failure |
| `conflicting.md` | Conflicting | 17 | Auto-select last used payment method at checkout |
| `partial-resolution.md` | Partial-resolution | 18 | Save payment details for returning customers |
| `unresolvable.md` | Unresolvable / park-at-cap | 19 | Localize checkout for international customers |
| `hidden-conflict.md` | Hidden-conflict | 20 | 30-minute order edit window after purchase |

## How to run a plan manually

1. Create a review session against the story instance
   (`POST /sessions`, story id, report formats per the plan's preconditions).
2. Walk the PO script top to bottom. Each turn is exactly one of:
   a message (read verbatim) or `po_accepted: true` — never both.
3. After each turn, check the row in "Turn-by-turn expectations": the
   facilitator's delegation (invoke / reuse_previous / open_issues), which
   artifacts were produced this turn (perspectives), the outcome, and the
   session state.
4. At the final turn, check "Expected final": session state, finalized-review
   contents, and the rendered report formats.

Turn 1 is always the facilitator's opening turn (`invoke="none"` by rule in
`schemas.md`); PO script turns therefore start at turn 2.

## Conventions

- Findings are asserted **semantically** (topic + severity), never as verbatim
  prose — wording legitimately varies across templates and reviewer runs.
- Park cap: the facilitator parks the session at the loop safety cap instead
  of evaluating readiness (`docs/design/agents.md`).
- Reports are rendered only on the finalize turn.
