# Partial-resolution (T1 story id 18: "Save payment details for returning customers")

Mirrors `docs/design/example-interaction.md` (story-04) turn-for-turn; that
document is the authoritative arc — this plan is its manual-test transcription.

## Preconditions

- Session on story id 18 (or any later rendering of this scenario).
- Report formats: `["md", "pdf"]`.
- Initial state: `active`; turn 1 = facilitator opening turn.

## Planted seeds (why this arc must happen)

- No consent/retention policy anywhere in the story → business gap (B-1).
- "Faster checkout" / conversion goal never operationalized as a measurable
  criterion → business gap (B-2, minor).
- Wording ("save payment details", "details are stored") implies storing card
  data; no tokenization mentioned → engineering blocker on PCI-DSS scope (E-1)
  and missing expired/removed-card behavior (E-2, minor).

## PO script (verbatim)

- **turn 2 (message):** "Yes — store a token from our PSP, never the raw card
  number. Success = checkout under 30 seconds for returning customers."
- **turn 3 (message):** "Add the 30-second criterion to the story's acceptance
  criteria. Also we keep cards 24 months max, noted in the consent text — that
  covers the retention gap."

## Turn-by-turn expectations

| # | What happens | Facilitator / orchestration expected | Artifacts (perspective, version) | Outcome | State after |
|---|---|---|---|---|---|
| 1 | Parallel reviews fan out; synthesis of v1+v1 | Opening turn: `invoke="none"` (by rule); presents synthesis, flags C-1, asks PO whether tokenization is an acceptable meaning of "save" | review-business v1, review-engineering v1, synthesis v1 | `continue` | active |
| 2 | PO message 1 (tokenization + 30s metric) | Delegates **engineering only** with extra context (PO confirmed PSP tokenization; define vault integration + expired-token behavior; metric: returning checkout < 30s); `reuse_previous=false`; `open_issues=["C-1"]`; readiness needs_work | review-engineering v2 (E-1 resolved; new minor: expired token falls back to normal checkout — answers old E-2); business v1 reused; synthesis v2: C-1 resolved, **new conflict C-2** (B-2 "not measurable" vs the PO's now-stated 30s metric not yet in the story) | `continue` | active |
| 3 | PO message 2 (add 30s to AC; 24-month retention in consent text) | No delegation: `invoke="none"`, `reuse_previous=false`, `open_issues=[]` — both remaining items resolved conversationally; resolutions recorded (C-2, B-1, B-2, E-1, E-2 → resolved); gate passes (no open issues, invoke none, no synthesis this turn) | — (dialogue only) | `finalize` | completed |

## Expected findings (semantic)

- Business v1: consent/retention policy missing (major); success metric
  missing / "faster" unmeasurable (minor).
- Engineering v1: PCI-DSS scope — raw storage prohibited, tokenized vault
  required (blocker); expired/removed saved-card behavior missing (minor).
- Conflicts: C-1 (business assumes storing for convenience vs engineering:
  raw storage prohibited) at turn 1; C-2 (story text lacks the PO's metric)
  surfaced at turn 2 re-synthesis; both resolved by turn 3.

## Expected final

- Session state: `completed` (turn 3, finalize).
- Finalized-review: `po_accepted=false` (normal readiness path); remaining
  open issues empty; synthesis v2 reference + dialogue resolutions.
- Reports: `md` + `pdf` rendered from the finalized review (this turn only).

## Format-invariance note

Any later rendering of this scenario (T2–T6) must produce the same arc:
same semantic findings and conflicts, same single-perspective delegation at
turn 2, same conversational resolution and finalize at turn 3. Only
info-level notes may differ.
