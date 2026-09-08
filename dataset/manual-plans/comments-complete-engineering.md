# Comments-complete-engineering (T1 story id 59: "Automatic retry for failed fulfillment-webhook deliveries")

Comment-completion: the description is engineering-thin (no retry policy)
but the comment thread carries the missing engineering substance. Both
reviews positive; arc identical to `clean`.

## Preconditions

- Session on story id 59 (t1-only comment scenario).
- Report formats: `["md", "pdf"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Business case solid in the description: 14 manual replays last quarter,
  ~3h each; consumer-side idempotency verified (pre-solved premise).
- Engineering seed: no retry attempts, no backoff, no retry window, no DLQ
  threshold in the description.
- Comments carry the missing policy: 5 attempts, backoff 1/5/15/60/300s
  (window under 7 minutes), delivery-id idempotent replays, DLQ after
  attempt 5, redelivery dashboard counter.

## PO script (verbatim)

- **turn 2 (`po_accepted: true`)** — no message, acceptance only.

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews fan out; synthesis of v1+v1 | Opening turn: `invoke="none"` (by rule); presents synthesis; no conflicts; readiness `ready`; asks the PO to accept. The engineering review incorporates the comment-thread policy — the gaps the description omits are supplied there | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO accepts | Finalization gate passes; finalized-review saved with `po_accepted=true`; reports rendered | finalized-review (+ md/pdf reports) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: positive; at most info-level notes.
- Engineering v1: POSITIVE — max info; the retry policy, idempotency
  semantics, DLQ threshold, and monitoring all arrive via comments. An
  engineering finding that the comments already answer is a failure of this
  case's point.
- Conflicts: none.

## Expected final

- Session state: `completed` (turn 2, finalize).
- Finalized-review: `po_accepted=true`; remaining open issues empty.
- Reports: `md` + `pdf` rendered on the finalize turn only.
