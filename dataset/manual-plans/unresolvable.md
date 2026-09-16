# Unresolvable / park-at-cap (T1 story id 19: "Localize checkout for international customers")

The story is deliberately unresolvable: every PO answer spawns new open
questions. The dialogue never converges; at the loop safety cap the
facilitator **parks** the session instead of evaluating readiness.

## Preconditions

- Session on story id 19 (or any later rendering of this scenario).
- Report formats: `["md"]` (never rendered — no finalize in this arc).
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Scope is explicitly "not defined" — markets, languages, currencies, and
  local payment methods all open.
- Three internal stakeholders with divergent demands and **no single owner**
  (sales: 5 markets this year; support: non-English tickets already
  multi-day; finance: no position on FX display pricing).
- Vague, untestable AC ("checkout is usable for them", "correct for that
  market").

## PO script (verbatim — answers stay deliberately partial/ambiguous)

- **turn 2:** "European markets, yes — the big ones first, then the rest."
- **turn 3:** "Languages: whatever sales needs for those markets, we'll see
  per market."
- **turn 4:** "Currencies: display in local currency where customers expect
  it; finance will work out the pricing later."
- **turn 5:** "Local payment methods: whatever the PSP supports, check with
  them."
- **turn 6:** "Support: they'll have to cope, sales promised the markets."
- **turn 7:** "Let's start with Germany and France as a pilot, but keep the
  others in scope."
- **turn 8:** "Germany and France first, everything else stays in the story."
- **turn 9:** "The markets stay open-ended — this is a roadmap story, the
  team should build for all of them."
- **turn 10:** "Keep going, we'll clarify as you build."

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Outcome | State after |
|---|---|---|---|---|
| 1 | Parallel reviews; synthesis v1 | Opening turn: `invoke="none"`; both perspectives raise gaps (business: no prioritization, no value metric, conflicting stakeholder demands; engineering: currencies/FX, localization, local methods, PSP support all undefined); synthesis flags multiple questions/conflicts; asks PO | `continue` | active |
| 2–5 | PO answers 1–4 | Each answer resolves one thread but opens new ones (which markets exactly? who translates? who owns FX pricing? which PSP methods where?); facilitator may delegate a perspective or continue dialogue — `open_issues` never empties; readiness stays needs_work; the turn's artifact set is **unpinned** (any delegation-produced set accepted; per-type version continuity asserted) | `continue` | active |
| 6–8 | PO answers 5–7 | Pilot answer (turn 7) contradicts the open-ended scope (turn 2) — a new conflict the next answer (turn 8) re-widens; still non-convergent | `continue` | active |
| 9 | PO answer 8 | Scope confirmed open-ended → the root cause (undefined scope, no owner) is now explicit; facilitator states the story cannot reach readiness in dialogue | `continue` | active |
| 10 | PO answer 9 ("keep going") | **Loop safety cap reached**: facilitator parks instead of evaluating readiness; remaining open issues recorded; no report rendered | `park` | parked |

## Expected findings (semantic)

- Business v1: no market prioritization / no measurable value (major);
  conflicting stakeholder demands with no owner (major).
- Engineering v1: currencies/FX undefined (major); localization and local
  payment methods unspecified (major); AC untestable as written (minor).
- Conflicts: recurring — pilot-scope vs open-ended-scope (turns 7–8) is the
  canonical re-eruption; `open_issues` nonempty on every non-final turn.

## Expected final

- Session state: `parked` (turn 10, park outcome).
- No finalized-review, no reports (reports exist only on finalize turns).
- Remaining open issues: nonempty, recorded in the park state.

## Format-invariance note

Any later rendering (T2–T6) must produce the same arc: non-convergent
dialogue, `open_issues` never empty, park at the loop safety cap. The number
of dialogue turns before the cap may vary by one; the **park outcome and
parked final state are invariant**.
