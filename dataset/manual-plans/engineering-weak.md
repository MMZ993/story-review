# Engineering-weak (T1 story id 14: "Automatic payment retry on PSP failure")

Engineering gaps found, business side solid — one engineering-side re-review
after the PO (with the payments team) supplies the missing retry policy.

## Preconditions

- Session on story id 14 (or any later rendering of this scenario).
- Report formats: `["md"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Business side complete and quantified: 38% of abandoned carts are payment
  errors, ~1/5 transient PSP failures, ~120 tickets/month, ~2 agent-days
  saved by halving; clear scope exclusions.
- Engineering gaps deliberately planted: "retries exhausted" is never
  specified (no max attempts, no backoff, no retry window); no idempotency
  guarantee (PSP idempotency keys) for retried charges; no behavior for the
  cart/order hold while retries run.
- No conflicts: business findings absent/positive; only engineering gaps.

## PO script (verbatim)

- **turn 2 (message):** "Retry policy from the payments team: max 3 attempts
  with exponential backoff (1s, 5s, 25s), every attempt carries the same PSP
  idempotency key per order, and the cart is held for 5 minutes from the
  first failure. Retries stop on success or decline as written."
- (No turn 3: the readiness gate finalizes the summary turn — see D30.)

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective, version) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews; synthesis v1 | Opening turn: `invoke="none"`; presents engineering findings (retry policy unspecified, idempotency missing, order-hold behavior undefined), business positive; no conflicts; asks PO for the retry policy | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO message 1 (retry policy) | Delegates **engineering only** with extra context (max 3 attempts, backoff 1s/5s/25s, PSP idempotency key per order, 5-minute cart hold); `reuse_previous=false`; post-delegation summary resolves every finding (`open_issues` empty) → **readiness gate finalizes same turn** (normal readiness path, `po_accepted=false`) | review-engineering v2 (gaps resolved against the policy); business v1 reused; synthesis v2; finalized-review + md report | `finalize` | completed |

## Expected findings (semantic)

- Engineering v1: retry policy unspecified — attempts/backoff/window missing
  (major); no idempotency guarantee for retried charges (major); cart/order
  hold during retries undefined (minor).
- Engineering v2: resolved against the PO-supplied policy.
- Business v1: positive; at most info-level notes.
- Conflicts: none.

## Expected final

- Session state: `completed` (turn 2, finalize via the readiness gate).
- Finalized-review: `po_accepted=false`; remaining open issues empty.
- Reports: `md` on the finalize turn only.

## Format-invariance note

Any later rendering (T2–T6) must produce the same arc: business positive,
engineering policy gaps, single engineering-only delegation after the PO
supplies the policy, readiness-gate finalize on the summary turn
(see D30).
