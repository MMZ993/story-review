# Hidden-conflict (T1 story id 20: "30-minute order edit window after purchase")

Both reviews are individually **positive** — yet their justifications rest
on contradictory assumptions, and only synthesis, holding both reviews,
detects it. No per-perspective findings; one cross-perspective conflict.

## Preconditions

- Session on story id 20 (or any later rendering of this scenario).
- Report formats: `["md"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- **Engineering hook** (Context): "The order pipeline captures payment
  immediately at order placement" — through the engineering lens a known,
  fine fact; the charge/refund-the-difference flow is straightforward against
  a captured payment. Review: positive.
- **Business hook** (Reason): "the customer's payment is only reserved during
  the day, so releasing the reservation is free" — through the business lens
  a fine cost justification. Review: positive.
- The hooks contradict: if capture is immediate there is no reservation to
  release (every total-reducing edit is a true PSP refund with fees); if
  payment is only reserved, the engineering approval collapses (the capture
  step must be redesigned). Both positive reviews cannot be right.

## PO script (verbatim)

- **turn 2 (message):** "Correction: capture stays immediate — the order
  pipeline does not reserve. Refund fees are accepted; cap it at one edit
  per order and make total-increasing edits re-authorize the card instead of
  assuming the free-reservation model."

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective, version) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews; synthesis v1 | Opening turn: `invoke="none"`; **both reviews positive** (at most info-level notes); synthesis flags **C-1** (needs_po_clarification): the business justification (free reservation release) and the engineering approval (immediate capture, refund API) rest on contradictory payment-capture models; asks the PO which model holds | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO message 1 (immediate capture confirmed, constraints added) | No delegation: `invoke="none"`, `reuse_previous=false`, `open_issues=[]` — resolution recorded against existing artifacts (business justification corrected: refund fees accepted; engineering scope adjusted conversationally: re-authorization for total-increasing edits); gate passes → finalize | — (dialogue only) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: positive; at most info-level notes.
- Engineering v1: positive; at most info-level notes.
- Conflicts: **C-1 at turn 1 with zero per-perspective findings** — this is
  the scenario's defining property; resolved at turn 2.

## Expected final

- Session state: `completed` (turn 2, finalize).
- Finalized-review: `po_accepted=false` (normal readiness path); remaining
  open issues empty.
- Reports: `md` on the finalize turn only.

## Format-invariance note

Any later rendering (T2–T6) must produce the same arc: two positive reviews,
one cross-perspective conflict at synthesis, conversational resolution,
finalize. Renderers must not "fix" the contradictory hooks — the
must-not-add list in the canonical facts forbids clarifying the capture
model, or the conflict disappears.
