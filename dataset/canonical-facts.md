# Canonical facts — per scenario

The single source of truth for each scenario's semantic content, per the
canonical content model in [`story-templates.md`](story-templates.md).
**Every template variant (T2–T6) is rendered from this document**, never
paraphrased from another variant. Rules:

- **must-retain**: every listed fact appears in the rendering (wording may
  vary; numbers, invariants, and scope exclusions verbatim-equivalent).
- **must-not-add**: nothing beyond the listed facts enters the rendering —
  especially the deliberate quality gaps that seed the scenario's review
  arc. "Fixing" a gap or adding an unlisted fact breaks the expected outcome.
- **title**: rendering target — the short designation below is used by T1/T2;
  templates that express the story sentence in the title (T3/T4) must still
  carry every title fact inside the body.
- **provenance**: ADO work-item ids are temporary authoring-time references
  (local decision D9) — the stable key is the scenario slug. T5 enabler
  counterparts are tracked separately in
  [`t5-enabler-spec.md`](t5-enabler-spec.md) (T5 is a work-item TYPE variant,
  excluded from cross-template invariance; its per-scenario ADO ids are
  42–48).

Scenario → review-arc: see [`manual-plans/`](manual-plans/) — the planted
gaps below are exactly the seeds each plan's arc requires.

## clean

- provenance: T1 id 5, T2 id 21, T3 id 28, T4 id 35, T6 id 49
- title: Invoice PDF in order confirmation email
- facts:
  - customers currently receive a plain-text order confirmation with no price breakdown
  - the order service already returns complete invoice data via `GET /orders/{id}`: line items, unit prices, VAT rates, totals
  - B2B customers and expense claims require a formal invoice document
  - top request from B2B account managers this quarter
  - order data is complete, so the work is rendering + attachment only
  - scope: invoice rendering and email attachment; out of scope: credit notes, self-service invoice re-download from the account page
  - invoice content is exactly the order data returned by `GET /orders/{id}` (line items, unit prices, VAT rates, totals) — no additional branding, legal, or localization requirements; invoices are single-language and single-currency (EUR)
  - email delivery failures other than hard bounces follow the existing email platform's standard delivery-failure handling (queued retries, provider bounce handling, operational alerting) — no story-specific behavior required; out of scope (Phase 9 dataset tuning: added because reviewers repeatedly flagged soft-bounce/transient-failure behavior as a gap)
  - parent Feature "Checkout Reliability" carries a description covering post-purchase reliability (confirmation-email pipeline, invoice delivery), complementing the epic's checkout-conversion goal (Phase 9 dataset tuning: both added so the clean story reads as genuinely aligned and complete)
- criteria:
  - order payment succeeded → confirmation email job sends the email within 2 minutes with the invoice PDF attached
  - invoice PDF rendered from the order API response → line items with unit prices, per-item VAT rate, and gross total match `GET /orders/{id}` exactly
  - hard-bouncing recipient address → email retried once after 5 minutes, then written to the mail audit log (no silent loss)
  - invoice rendering failure → email still sent without the attachment; failure on the alerting dashboard; no customer-visible error
- must-not-add: no facts, dependencies, links, deadlines, contacts, or sign-off beyond the above.

## business-weak

- provenance: T1 id 10, T2 id 22, T3 id 29, T4 id 36, T6 id 50
- title: Google Pay at checkout
- facts:
  - the PSP exposes Google Pay in its gateway API (`POST /payment-intents`, method `google_pay`)
  - the web checkout can render the button via the PSP's JS SDK
  - the checkout payment-list flow is the existing integration point
  - justification: competitors have it and customers keep asking for more payment options at checkout
  - no adoption target or success metric is set; no demand data beyond
    anecdotal requests, success reviewed informally after launch (Phase 9
    dataset tuning, t1 only: stated explicitly because reviewers rated the
    implicit vagueness `info` instead of the intended `major` gap)
  - the Google Pay button uses the PSP SDK's default presentation, no
    custom styling or branding work (Phase 9 dataset tuning, t1 only:
    settles presentation territory)
  - scope: add the method to the existing checkout payment-list flow; out of scope: other payment methods, native apps
- criteria:
  - PSP SDK reports Google Pay availability in a browser → button shown when the payment step renders; hidden otherwise
  - customer selects Google Pay → payment intent created with method `google_pay`; existing payment flow completes; order state machine unchanged
  - failed or cancelled intent → flow returns to the payment-list step, previous selection cleared, no order state change, failure logged with the PSP correlation ID
  - method enabled → checkout e2e suite and accessibility checks pass; button keyboard-accessible
- must-not-add: **no target segment, no measurable success criterion, no
  quantified demand, no priority rationale** — the weak business case is the
  scenario's seed and must stay vague (the PO supplies it at review time per
  the manual plan).

## engineering-weak

- provenance: T1 id 14, T2 id 23, T3 id 30, T4 id 37, T6 id 51
- title: Automatic payment retry on PSP failure
- facts:
  - a temporary PSP outage (timeout, 5xx) fails the order outright today: customer sees an error, cart abandoned, support tickets follow
  - the order service already distinguishes PSP decline from PSP error, so a legitimate retry is identifiable
  - payment errors were 38% of abandoned carts last quarter; the payments team estimates roughly a fifth are transient PSP failures
  - support receives ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month
  - scope: automatic retry for PSP errors only; out of scope: retries for declines, changes to the decline messaging, native apps
- criteria:
  - payment failed due to PSP error (not decline) → system retries automatically without customer action
  - retried payment succeeds, or failure is a decline → retries stop immediately
  - retries exhausted and last attempt fails → customer sees the standard payment-failed page; order remains recoverable from the cart
  - any retried payment completes (success or final failure) → retry outcome visible in the existing payments dashboard
- must-not-add: **no retry policy specifics** — no max attempts, backoff,
  retry window; no idempotency guarantee (PSP idempotency keys); no
  cart/order-hold behavior during retries (the PO supplies the policy at
  review time per the manual plan).

## conflicting

- provenance: T1 id 17, T2 id 24, T3 id 31, T4 id 38, T6 id 52
- title: Auto-select last used payment method at checkout
- facts:
  - checkout currently shows all available payment methods with no default; returning customers re-pick their method on every order
  - the one-page checkout redesign under this feature aims to remove checkout steps
  - the redesign's step budget: checkout must reach payment confirmation
    with at most one customer interaction after the page loads (Phase 9
    dataset tuning, t1 only: sharpens the planted conflict — reviewers
    rated both seeds below `major` when the collision was only implicit)
  - funnel analytics: returning customers spend a median 11 seconds selecting a payment method they used on the previous order
  - UX research flagged method selection as the top friction point for returning customers; marketing asked for a "one-tap pay" experience
  - scope: web checkout for signed-in returning customers; out of scope: guest checkout, native apps, adding new payment methods
- criteria:
  - returning customer with a previously used method, checkout loads → last used method pre-selected
  - pre-selected method, customer confirms the order → payment charged with that method **without a separate selection step**
  - last used method no longer available, checkout loads → no method pre-selected; message explains why
- must-not-add: **no explicit confirmation action, no visible Pay button, no
  method-change mechanism, no "pre-selected method and total shown" criterion**
  — the unmitigated charge-without-selection-step (business risk) vs the
  step-removal requirement (engineering constraint) is the planted conflict;
  the PO resolves it at review time per the manual plan.

## partial-resolution

- provenance: T1 id 18, T2 id 25, T3 id 32, T4 id 39, T6 id 53 (mirrors `docs/design/example-interaction.md` story-04)
- title: Save payment details for returning customers
- facts:
  - returning customers re-enter full card details on every order; checkout for returning customers averages 2m40s; no payment data is stored today
  - Q4 growth goal: +15% conversion for returning customers
  - payment-data entry is the 3rd-highest drop-off point in funnel analytics
  - scope: web checkout, cards via the current PSP; out of scope: native apps, wallets, bank transfers
- criteria:
  - returning customer with saved payment details reaches checkout → saved method available for selection without re-entering card details
  - customer opts to save payment details, payment completes → details stored for future checkouts
  - saved method used at checkout, payment completes → customer reaches the confirmation page
- must-not-add: **no consent/retention policy; no tokenization, PCI-DSS, or
  raw-storage handling; no expired/removed-card behavior; "faster checkout"
  must not become a measurable criterion** — these gaps (B-1/B-2/E-1/E-2 in
  the example interaction) are the scenario's seeds, resolved only through
  the PO dialogue per the manual plan.

## unresolvable

- provenance: T1 id 19, T2 id 26, T3 id 33, T4 id 40, T6 id 54
- title: Localize checkout for international customers
- facts:
  - checkout is English-only, EUR-only, offers cards and PayPal only
  - the shop already ships to several EU markets; checkout has not followed the international expansion
  - sales wants five additional markets live this year
  - support reports non-English tickets already take days to resolve
  - finance has no position on display currencies and FX pricing
  - there is no single owner for international checkout
  - scope: **not defined** — markets, languages, currencies, local payment methods all open
- criteria (deliberately vague/untestable):
  - international customer reaches checkout → checkout is usable for them
  - prices displayed in a non-EUR market → correct for that market
  - international order placed → can be fulfilled like a domestic one
- must-not-add: **no scope narrowing, no owner assignment, no stakeholder
  reconciliation, no operational definition of the criteria** — the story
  must stay unresolvable so the facilitator parks it at the loop safety cap
  per the manual plan.

## hidden-conflict

- provenance: T1 id 20, T2 id 27, T3 id 34, T4 id 41, T6 id 55
- title: 30-minute order edit window after purchase
- facts (both contradictory capture statements are canonical and must both survive, unreconciled):
  - customers cannot modify an order (address, size, quantity) after checkout completes; the only path today is cancel-and-reorder or a support ticket
  - **the order pipeline captures payment immediately at order placement** (engineering hook)
  - support handles ~90 order-change tickets per week; cancel-and-reorder loses a share of those orders entirely
  - CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%
  - **payment handling carries no cost: the customer's payment is only reserved during the day, so releasing the reservation is free** (business hook)
  - scope: edits to shipping address and item size/quantity; out of scope: changing the payment method, subscription orders, native apps
- criteria:
  - completed order, edit requested within 30 minutes → order updated in place, no new order created
  - edit changes the order total → customer automatically charged or refunded the difference
  - edit requested after the 30-minute window → customer told to contact support
- must-not-add: **nothing may clarify or reconcile the payment-capture
  model; no refund fees, re-authorization, or edit-count limits** (those are
  the PO's review-time resolution per the manual plan); both reviews must be
  individually positive — the contradiction is only visible to synthesis.
