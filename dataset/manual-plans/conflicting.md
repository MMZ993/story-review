# Conflicting (T1 story id 17: "Auto-select last used payment method at checkout")

Business and engineering findings contradict; synthesis flags the conflict;
the PO resolves it **conversationally, without any re-review delegation** —
this is what distinguishes the arc from partial-resolution.

## Preconditions

- Session on story id 17 (or any later rendering of this scenario).
- Report formats: `["md"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds

- Business-side risk (planted in AC 2: "charged … without a separate
  selection step"): charging on a pre-selected method with no explicit step
  is an accidental-purchase/chargeback exposure — a business reviewer will
  demand an explicit confirmation action.
- Engineering-side constraint (planted in Context: "the one-page checkout
  redesign … aims to remove checkout steps"): keeping a separate selection
  step defeats the redesign and breaks its latency/step budget — an
  engineering reviewer will insist the step must go.
- The two demands are mutually exclusive as stated → synthesis conflict.

## PO script (verbatim)

- **turn 2 (message):** "Keep the pre-selection, and keep the single 'Pay'
  button as the explicit action: the customer always confirms the order with
  the pre-selected method visibly shown, and can change it with one tap. That
  removes the selection *step* but never charges without one explicit
  customer action. Add a criterion: the pre-selected method and total are
  visible on the Pay button."

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective, version) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews; synthesis v1 | Opening turn: `invoke="none"`; presents both findings and flags **C-1** (needs_po_clarification): business demands an explicit selection step vs engineering requires its removal; asks the PO to decide | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO message 1 (pre-select + explicit Pay action) | **No delegation**: `invoke="none"`, `reuse_previous=false`, `open_issues=[]` — the resolution reconciles both findings against the existing artifacts (the confirm-order action the redesign already includes satisfies the business demand); resolutions recorded (C-1, B, E → resolved) | — (dialogue only) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: charging without a separate selection step = accidental
  purchase / chargeback exposure; an explicit confirmation action is required
  (major).
- Engineering v1: retaining the explicit selection step breaks the one-page
  checkout redesign's step/latency budget (major).
- Conflicts: C-1 at turn 1 — the two majors contradict; resolved at turn 2
  by the PO's distinction (selection step removed, explicit Pay action kept).

## Expected final

- Session state: `completed` (turn 2, finalize).
- Finalized-review: `po_accepted=false` (normal readiness path); remaining
  open issues empty.
- Reports: `md` on the finalize turn only.

## Note on two acceptable script variants

Two legitimate closings exist for this scenario and the expected file must
pick one:

1. **2-turn** (the plan above): the PO's turn-2 message resolves everything
   conversationally → finalize at turn 2, `po_accepted=false`, normal path.
2. **3-turn**: the facilitator asks the PO to confirm acceptance after the
   resolution → `po_accepted=true` at turn 3 → finalize at turn 3.

The manual plan prefers variant 1 (shorter, exercises conversational
resolution + finalize gate without delegation). Record the chosen variant in
the expected file; both are contract-legal.

## Format-invariance note

Any later rendering (T2–T6) must produce the same arc: contradictory major
findings, C-1 at synthesis, conversational resolution, finalize. Formatting
may add info-level notes only.
