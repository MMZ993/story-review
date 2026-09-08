# Comments-benign (T1 story id 57: "VAT breakdown table in the order confirmation email")

Comment-invariance: a clean story plus a benign, resolved Q&A thread — the
comments must NOT create findings. Arc identical to `clean`.

## Preconditions

- Session on story id 57 (t1-only comment scenario; no other rendering).
- Report formats: `["md", "pdf"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Description is fully clean: quantified support demand (~30 vat-tagged
  tickets/month), engineering pre-solved (order API returns per-item VAT),
  edge paths in AC (missing VAT row, mixed rates).
- The comment thread is pure noise for the verdict: scope question answered
  (email only), legal confirmation (no mandated layout). Resolved Q&A.

## PO script (verbatim)

- **turn 2 (`po_accepted: true`)** — no message, acceptance only.

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews fan out; synthesis of v1+v1 | Opening turn: `invoke="none"` (by rule); presents synthesis; no conflicts; readiness `ready`; asks the PO to accept. The comment thread is included as story context and produces no findings | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO accepts | Finalization gate passes; finalized-review saved with `po_accepted=true`; reports rendered | finalized-review (+ md/pdf reports) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: positive; at most info-level notes.
- Engineering v1: positive; at most info-level notes.
- Conflicts: none.
- Comment-invariance: any finding that cites the comment thread as a gap is
  a failure of this case's point (the thread is benign and resolved).

## Expected final

- Session state: `completed` (turn 2, finalize).
- Finalized-review: `po_accepted=true`; remaining open issues empty.
- Reports: `md` + `pdf` rendered on the finalize turn only.
