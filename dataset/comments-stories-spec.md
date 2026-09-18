# Comments stories spec (extension 1: comments as review input)

Status: AUTHORING SPEC (session 16, owner-approved: 3 stories, T1 only).
Source plan: `docs-local/plans/dataset-extensions-comments-linked-stories.md`
(extension 1). Design: `docs/design/schemas.md` `StoryComment`; dataset
envelope `comments` (D9 amendment 3). This file is the authoring input for
the three comment stories AND carries their provenance lines (consumed by
`dataset/tools/export_ado.py`, like `t5-enabler-spec.md`).

## Framing (all three stories)

- Comments are **semantic review input**: reviewers must read the thread as
  part of the story context. C-1 proves comments must NOT create findings;
  C-2 proves comments can resolve ONE side; C-3 proves comments can carry
  the missing engineering substance.
- All comments are authored by one real user — anonymized by the export to
  the single "Story Author" persona (owner decision, Runbook 08 spike).
  Thread texts are therefore phrased so the dialogue reads naturally despite
  the single anonymized author (self-answered notes, Q&A recorded in one
  thread).
- The story description itself must NOT contain the information that lives
  in the comments (that is the point of each arc) — except C-1, whose
  description is fully clean and whose comments are pure noise.
- Case ids / story ids (t1-only scenarios): `t1/comments-benign` =
  story-43, `t1/comments-clarify-business` = story-44,
  `t1/comments-complete-engineering` = story-45. NOTE (review I-1): these
  are NOT produced by the template-major formula — appending to `SLUGS`
  would renumber all 42 existing ids. `story_id_for` needs a t1-only
  branch: core slugs (indices 0–6) keep the stride-7 formula; extension
  slugs get `story-{43 + (index - 7)}`. `EXPECTED_STORIES` becomes 45 at
  implementation.

## comments-benign

Same world discipline as `clean`: complete, quantified business case;
engineering pre-solved; edge paths in AC. Comments are a benign, resolved
Q&A that must NOT change the verdict (comment-invariance). C-1.

- provenance: T1 id 57, scenario comments-benign
- title: VAT breakdown table in the order confirmation email
- facts (description):
  - the confirmation email today lists totals only; customers opening
    expense claims ask support for the VAT split (~30 tickets/month,
    measurable: tickets with the "vat" tag)
  - `GET /orders/{id}` already returns per-item VAT rates and amounts, so
    this is email-template rendering only — no backend change
  - scope: add the VAT breakdown table to the confirmation email template;
    out of scope: invoice PDF (separate story), credit notes
- criteria:
  - order payment succeeded → confirmation email contains a VAT breakdown
    table whose per-item rates and amounts match `GET /orders/{id}` exactly
  - mixed VAT rates in one order → each line shows its own rate; totals
    cross-check against the order API response
  - VAT data missing for an item → email sent without the row, gap logged to
    the mail audit log; no customer-visible error
- must-not-add: nothing beyond the above; no deadlines, contacts, links.
- comments (3, chronological):
  1. "Question: should the table also appear in the order-history page, or
     email only?" 
  2. "Answer: email only for now — the order-history page is out of scope
     (tracked separately)."
  3. "Note: legal confirmed there is no mandated VAT layout for
     transactional email; the template team's standard table is fine."
  4. "Note: any failure of the order API itself (timeout, 5xx, network
     error) follows the existing confirmation-email job's standard failure
     handling (retry, ops alerting) — out of scope; only per-item VAT-data
     gaps are handled by this story." (Phase 9 dataset tuning: reviewers
     minted the whole-API failure as `major` over the info ceiling)
- expected verdict: BOTH reviews positive (max info); readiness `ready` at
  turn 1; arc identical to `clean` (accept at turn 2). Expected file =
  clean arc with a comment-invariance note.

## comments-clarify-business

Story is ambiguous for BOTH perspectives in the description; the comment
thread resolves the BUSINESS side only (target segment, success criterion,
priority rationale supplied in comments) — the business review must come
back positive *because of the comments*; the engineering gaps stay (no
split-ordering rule, no refund/chargeback behavior, no PSP capability
confirmation) and drive the arc exactly like `engineering-weak`. C-2.

- provenance: T1 id 58, scenario comments-clarify-business
- title: Split payment: gift card + card at checkout
- facts (description — deliberately weak on both sides):
  - customers with a gift-card balance cannot combine it with a card
    payment at checkout; they ask support to burn the card in a separate
    transaction
  - the checkout payment-list flow is the existing integration point
  - scope: allow paying with one gift card + one card in one order; out of
    scope: multiple gift cards, native apps
- criteria (thin, like engineering-weak's seed):
  - customer applies a gift card with insufficient balance → remaining
    amount payable by card; order completes in one payment step
  - gift-card balance covers the full total → card step skipped entirely
- must-not-add (in the DESCRIPTION): no target segment, no success
  criterion, no priority rationale (business weakness is the seed) AND no
  split-ordering rule, no refund/chargeback behavior, no PSP capability
  statement (engineering weakness is the seed). The PO supplies the
  business side via… nothing here — the comments carry it.
- comments (3, chronological) — carry the BUSINESS clarifications only:
  1. "Note from discovery: 18% of gift-card holders abandoned checkout last
     quarter with a partial-balance card in cart (analytics funnel report);
     support logged 210 such contacts this year."
  2. "Priority rationale: gift-card sales grew 40% YoY; retention team
     flagged combined-payment as the top driver of gift-card complaints in
     Q3."
  3. "Success criterion: cut the partial-balance checkout abandonment (18%
     baseline) by half within two quarters of release."
  4. "UX follow-up: an applied gift card can be removed again before the
     customer confirms the order (standard remove control, full amount back
     on the card step). Any payment failure shows the existing
     payment-failure page — no new failure UX in this story." (Phase 9
     dataset tuning: kills business-side `minor` mints; engineering
     findings E-1/E-2 stay — transactional/refund semantics untouched)
- expected verdict: business review POSITIVE (max info — the comments
  supply segment, demand, rationale, criterion); engineering review carries
  the findings: E-1 (major) split-ordering rule unspecified — which
  instrument is charged first, partial-capture semantics; E-2 (major)
  refund/chargeback behavior for a two-instrument payment undefined; E-3
  (minor) no confirmation the PSP supports split payment in one checkout
  flow. Arc identical to `engineering-weak` (3 turns: findings → PO
  supplies policy → engineering re-review → accept), except the PO's turn-2
  message answers the engineering side (the business side was never open).
- draft PO turn-2 message (verbatim script input, mirrors
  engineering-weak's policy answer): "Policy for the open points: charge
  the gift card first, capture the remainder on the card in the same
  payment step (partial capture, one order state machine). Refunds go back
  to the original instruments proportionally, gift card first; chargebacks
  follow the PSP's existing card process with the gift-card part written
  off against the loyalty ledger. And yes — the PSP confirmed split
  payment in one checkout flow is supported on our plan (ticket with their
  support, capability checked last sprint)."

## comments-complete-engineering

Description carries a solid business case but is deliberately
engineering-thin (like `engineering-weak`'s seed: no delivery policy); the
comment thread carries the missing engineering specifics (attempts, backoff,
idempotency, monitoring) — the engineering review must incorporate the
thread and come back positive (comment-completion). C-3.

- provenance: T1 id 59, scenario comments-complete-engineering
- title: Automatic retry for failed fulfillment-webhook deliveries
- facts (description):
  - the warehouse fulfillment service consumes order events via a webhook;
    when it is down, deliveries fail and orders sit unfulfilled until
    manual replay (ops ran 14 manual replays last quarter, ~3h each)
  - webhook payloads are already idempotent on the consumer side (event id
    deduplication verified by the platform team)
  - scope: automatic redelivery for failed webhook deliveries; out of
    scope: webhook payload changes, new consumer endpoints
- criteria (thin — no retry policy in the description):
  - delivery fails (timeout, 5xx) → system redelivers automatically without
    manual action
  - redeliveries exhausted → event lands on the dead-letter queue and pages
    the on-call integration owner; nothing silently lost
- must-not-add (in the DESCRIPTION): no retry attempts, no backoff, no
  retry window, no DLQ thresholds (the comments carry them).
- comments (3, chronological) — carry the ENGINEERING specifics:
  1. "Retry policy agreed with the platform team: 5 attempts, exponential
     backoff 1/5/15/60/300s, total window under 7 minutes."
  2. "Idempotency: redeliveries reuse the same delivery id; the consumer's
     event-id dedup makes replays safe (already verified)."
  3. "DLQ threshold: move to dead-letter after attempt 5; dashboard: new
     'webhook redeliveries' counter on the existing integrations board."
  4. "Terminal client errors: HTTP 4xx responses from the webhook endpoint
     are not retried — they land on the dead-letter queue flagged
     'terminal-client-error' for investigation, same as exhausted
     redeliveries." (Phase 9 dataset tuning: reviewers minted 4xx handling
     as `minor` over the info ceiling)
- expected verdict: engineering review POSITIVE (max info — policy,
  idempotency, DLQ, monitoring all present via comments); business review
  positive (quantified case in the description). Arc identical to `clean`
  (ready at turn 1, accept at turn 2). Known duplication (review M-2,
  kept deliberately): consumer-side idempotency is stated in the
  description as a pre-solved premise (like engineering-weak's
  "order service already distinguishes decline from error") while comment 2
  reiterates it — the *policy* substance (attempts/backoff/DLQ/dashboard)
  stays comment-only.

## Integration notes (implementation checklist)

- Headings in this file are single-token scenario slugs and provenance
  lines live INSIDE each section — that is what `provenance_map()` parses
  (review I-2). ADO ids are assigned at authoring time; update the three
  provenance lines to the actual ids after `az boards work-item create`.
- `export_ado.py`: register this file in `provenance_map()` sources; extend
  `story_id_for` per the note above (t1-only branch, ids 43–45);
  `EXPECTED_STORIES` 42 → 45; comments attach automatically when present.
- Loader: extend the `Scenario` pattern with the three slugs; the
  matrix-completeness invariant becomes "core grid T1–T6 × 7 scenarios,
  plus t1-only comment scenarios" (each t1-only slug must appear exactly
  once, in t1).
- Expected files: three new scenario-canonical files
  (`comments-benign.json`, `comments-clarify-business.json`,
  `comments-complete-engineering.json`), `invariance.
  applies_across_templates: false`.
- Manual plans: three entries in `dataset/manual-plans/` following the
  existing per-scenario format.

## Phase 9 dataset repairs (2026-09-16)

- The three ADO work items were authored **without the acceptance
  criteria** this spec defines (run-23 root cause for the comments
  severity cluster; D30). PATCHed 2026-09-16 with the criteria above,
  verbatim in Given/when/then form (revs 5/5/6).
- `comments-clarify-business` arc adapted per D30: no trailing acceptance
  turn; readiness-gate finalize on the post-delegation summary turn.
- `docs/quality/mock-data.md`: comment-scenario rows for the scenario table
  (docs commit, separate and atomic).
