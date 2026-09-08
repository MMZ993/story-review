# Comments-clarify-business (T1 story id 58: "Split payment: gift card + card at checkout")

One-sided comment clarification: the description is ambiguous for BOTH
perspectives; the comment thread resolves the BUSINESS side only. Business
review must be positive *because of the comments*; the engineering gaps
drive an `engineering-weak` arc.

## Preconditions

- Session on story id 58 (t1-only comment scenario).
- Report formats: `["md"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Description deliberately weak on both sides: no target segment, no
  success criterion, no priority rationale (business seed) AND no
  split-ordering rule, no refund/chargeback behavior, no PSP capability
  statement (engineering seed).
- Comments carry the business side only: 18% partial-balance abandonment,
  210 support contacts this year, 40% YoY gift-card growth, halving
  criterion within two quarters.

## PO script (verbatim)

- **turn 2 (message)** — "Policy for the open points: charge the gift card
  first, capture the remainder on the card in the same payment step (partial
  capture, one order state machine). Refunds go back to the original
  instruments proportionally, gift card first; chargebacks follow the PSP's
  existing card process with the gift-card part written off against the
  loyalty ledger. And yes — the PSP confirmed split payment in one checkout
  flow is supported on our plan (ticket with their support, capability
  checked last sprint)."
- **turn 3 (`po_accepted: true`)** — no message, acceptance only.

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews fan out; synthesis of v1+v1 | Opening turn: `invoke="none"` (by rule); engineering findings presented, business POSITIVE (comments supplied the case); no conflicts; PO asked for the split policy | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO supplies the split-payment policy | Engineering-only delegation (`invoke="engineering"`), PO message as extra context; business v1 reused (never open); readiness `needs_work` | review-engineering v2, synthesis v2 | `continue` | active |
| 3 | PO accepts | Finalization gate passes; finalized-review with `po_accepted=true` | finalized-review (+ md report) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: POSITIVE — max info; the comment thread resolves what the
  description omits. A business finding that ignores the comments is a
  failure of this case's point.
- Engineering v1:
  - E-1 (major): split-ordering rule unspecified — which instrument is
    charged first, partial-capture semantics (resolved turn 2)
  - E-2 (major): refund/chargeback behavior for a two-instrument payment
    undefined (resolved turn 2)
  - E-3 (minor): no confirmation the PSP supports split payment in one
    checkout flow (resolved turn 2)
- Conflicts: none.

## Expected final

- Session state: `completed` (turn 3, finalize).
- Finalized-review: `po_accepted=true`; remaining open issues empty.
- Reports: `md` rendered on the finalize turn only.
