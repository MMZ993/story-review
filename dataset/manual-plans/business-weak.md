# Business-weak (T1 story id 10: "Google Pay at checkout")

Business gaps found, engineering side solid — one business-side re-review
after the PO supplies the missing business case.

## Preconditions

- Session on story id 10 (or any later rendering of this scenario).
- Report formats: `["md"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Engineering side pre-solved and explicit: PSP gateway endpoint + JS SDK
  named, availability gating, failure/cancel path with order-state
  invariants, PSP correlation ID logging, e2e + accessibility criteria.
- Business justification is the weak part: "Competitors have it and customers
  keep asking" — no target segment, no measurable success criterion, no
  quantified demand, no priority rationale.
- No conflicts: engineering findings are absent/positive; only business gaps.

## PO script (verbatim)

- **turn 2 (message):** "Target is Android web traffic — 31% of checkout
  sessions, and post-purchase surveys name Google Pay most often. Success =
  checkout conversion for Android users +2pp within two months of launch.
  Priority: this quarter, before the holiday peak."

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective, version) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews; synthesis v1 | Opening turn: `invoke="none"`; presents business findings (value not justified/measurable), engineering positive; no conflicts; asks PO for the business case | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO message 1 (segment, metric, deadline) | Delegates **business only** with extra context (Android segment, +2pp conversion target, holiday-peak deadline); `reuse_previous=false`; post-delegation summary resolves every finding (`open_issues` empty) → **readiness gate finalizes same turn** (normal readiness path, `po_accepted=false`) | review-business v2 (gaps resolved against the supplied case); engineering v1 reused; synthesis v2; finalized-review + md report | `finalize` | completed |

## Expected findings (semantic)

- Business v1: no measurable success criterion (major); justification by
  competitor parity rather than own demand data (major); no target segment
  named (minor).
- Business v2: resolved against the PO-supplied case.
- Engineering v1: positive; at most info-level notes.
- Conflicts: none.

## Expected final

- Session state: `completed` (turn 2, finalize via the readiness gate).
- Finalized-review: `po_accepted=false`; remaining open issues empty.
- Reports: `md` on the finalize turn only.

## Format-invariance note

Any later rendering (T2–T6) must produce the same arc: engineering positive,
business value gaps, single business-only delegation after the PO supplies
the case, single business-only delegation after the PO supplies the case,
readiness-gate finalize on the summary turn (no separate acceptance turn;
see D30).
