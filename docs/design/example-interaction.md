# Example Interaction — End-to-End Conflict Resolution

A concrete walkthrough of one story lifecycle, using the contract vocabulary of
[schemas.md](schemas.md) and the flows of [data-flow.md](data-flow.md). It corresponds
to the **partial-resolution scenario** in [../quality/mock-data.md](../quality/mock-data.md);
the same interaction is replayed by the evaluation suite from its expected-file script
(see the expected-file contract there) and shown live in the demo.

Story `story-04` — *"As a returning customer, I want to save my payment details so that
checkout is faster."*

## 1. Story selection and initial parallel review (flow 1)

`POST /sessions` (story-04, formats `["md","pdf"]`) → `story_run_id = run-7c1a…`,
parallel fan-out, no PO dialogue yet.

**Business Reviewer** (`ReviewReport`, perspective `business`):

- `B-1` *(major)* No consent/retention policy for storing payment data — unclear
  business justification and regulatory exposure.
- `B-2` *(minor)* "Faster checkout" is not measurable — no success metric in the
  acceptance criteria.

**Engineering Reviewer** (`ReviewReport`, perspective `engineering`):

- `E-1` *(blocker)* PCI-DSS scope: storing raw PANs is prohibited; requires a
  tokenized vault integration, not a database column.
- `E-2` *(minor)* Missing behavior for expired/removed saved cards at checkout.

## 2. Synthesis detects the conflict (flow 1)

`SynthesisReport`:

- `C-1` *(needs_po_clarification)* — **B-1 vs E-1**: business assumes we store the
  card for convenience; engineering states raw storage is prohibited. The story's
  intent (convenience) and its wording ("save my payment details") conflict.
- Merged findings `B-2`, `E-2`; questions for PO: "Is tokenization via the payment
  provider an acceptable interpretation of 'save'?"

Facilitator opening turn (turn 1, `invoke="none"` by rule) presents the synthesis,
flags `C-1`, and asks the PO the clarification question. Outcome `continue`.

## 3. PO clarifies; facilitator delegates one side (flow 2)

PO (turn 2): *"Yes — store a token from our PSP, never the raw card number. Success =
checkout under 30 seconds for returning customers."*

Facilitator `DelegationDecision`:

```json
{
  "invoke": "engineering",
  "extra_context": "PO confirmed PSP tokenization; define vault integration and expired-token behavior. Success metric: returning checkout < 30s.",
  "reuse_previous": false,
  "open_issues": ["C-1"],
  "readiness": "needs_work"
}
```

Orchestration invokes **only** the engineering reviewer with the extra context; the
business artifact is reused untouched (paired as the latest per perspective).

**Engineering re-review** produces `review-engineering` v2: `E-1` resolved via PSP
vault tokens; new finding `E-3` *(minor)* — expired token must fall back to normal
checkout (answers the old `E-2`).

**Re-synthesis** pairs business v1 + engineering v2: `C-1` resolved (recorded in
`resolved_from_previous`); new conflict `C-2` — `B-2`'s "not measurable" vs the PO's
now-stated 30-second metric: the story text hasn't been updated to include it.
Outcome `continue` (synthesis produced this turn; facilitator evaluates next turn).

## 4. Second clarification resolves without delegation (flow 2)

PO (turn 3): *"Add the 30-second criterion to the story's acceptance criteria. Also
we keep cards 24 months max, noted in the consent text — that covers B-1's retention
gap."*

Facilitator `DelegationDecision`: `invoke="none"`, `reuse_previous=false`,
`open_issues=[]` — both remaining items are resolved conversationally against the
existing artifacts; no reviewer re-run needed.

Resolutions recorded as `ResolutionItem`s (`C-2 → resolved`, `B-1 → resolved`,
`E-1 → resolved` …). Gate: `open_issues` empty, `invoke=none`, no synthesis this
turn → outcome `finalize`.

## 5. Finalization (flow 3)

Orchestration saves the deterministic `finalized-review` artifact (synthesis v2
reference + dialogue resolutions + `po_accepted=false`, normal readiness path,
remaining issues empty), the report server renders MD and PDF from it, and the
session transitions `finalizing → completed`. The response returns both
`ReportDownload`s with expiring signed URLs.

## What this example demonstrates

- parallel reviews exposing one business-side and one engineering-side gap;
- conflict detection (`C-1`) between the two viewpoints;
- PO clarification driving **single-perspective delegation** with `extra_context`;
- re-synthesis pairing the new artifact with the untouched other perspective and
  surfacing a follow-on conflict (`C-2`);
- conversational resolution without delegation, the finalization gate, and the
  finalized-review-based report — the full Pattern 3 loop inside Pattern 1/2 flows.
