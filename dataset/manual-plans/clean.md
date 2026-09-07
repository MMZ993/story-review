# Clean (T1 story id 5: "Invoice PDF in order confirmation email")

Happy path — both reviews positive, story reaches `ready` quickly and is
accepted.

## Preconditions

- Session on story id 5 (or any later rendering of this scenario).
- Report formats: `["md", "pdf"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Complete, quantified business justification (B2B demand, formal invoice
  requirement, top request from account managers).
- Engineering side pre-solved: order API already returns complete invoice
  data; scope is rendering + attachment only.
- Failure/edge paths are explicit in the AC: hard bounce (retry + audit log),
  rendering failure (email still sent, alert raised, no customer error).
- Measurable criterion: email within 2 minutes; PDF content matches
  GET /orders/{id} exactly.

## PO script (verbatim)

- **turn 2 (`po_accepted: true`)** — no message, acceptance only.

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews fan out; synthesis of v1+v1 | Opening turn: `invoke="none"` (by rule); presents synthesis; no conflicts; readiness `ready`; asks the PO to accept | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO accepts | Finalization gate passes (no open issues, invoke none, no new synthesis); finalized-review saved with `po_accepted=true`; reports rendered | finalized-review (+ md/pdf reports) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: positive; at most info-level notes (e.g. wording of the
  invoice template).
- Engineering v1: positive; at most info-level notes.
- Conflicts: none.

## Expected final

- Session state: `completed` (turn 2, finalize).
- Finalized-review: `po_accepted=true`; remaining open issues empty.
- Reports: `md` + `pdf` rendered on the finalize turn only.

## Format-invariance note

Any later rendering of this scenario (T2–T6) must yield the same arc:
positive reviews, readiness `ready`, accept at the first PO turn, finalize.
Formatting may add info-level notes only.
