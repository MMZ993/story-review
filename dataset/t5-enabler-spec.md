# T5 enabler spec — per scenario

Authoring input for the T5 column (enabler / technical stories). Unlike
T2–T6, T5 items are **not renderings of the user-actor canonical facts**
([`canonical-facts.md`](canonical-facts.md)) — each is a self-contained
enabler story, written fresh, and excluded from cross-template invariance
assertions (see the matrix section in [`story-templates.md`](story-templates.md)).

**Design decision (owner-approved, session 14):** each enabler is the
engineering-side counterpart of its scenario — it lives in the same story
world, addresses the same underlying problem, and **preserves the scenario's
quality flaw verbatim**, so the expected review arc and verdict class match
the scenario's manual plan exactly (same test results as the T1–T4 column;
the actor and value wording differ, the outcome must not).

Rules (mirroring the canonical model):

- **must-retain**: every listed fact appears in the story.
- **must-not-add**: nothing beyond the listed facts — especially the planted
  flaw must not be softened, fixed, or clarified.
- **framing**: "As the engineering team / a system actor, we need ... so that
  ..." — non-user-facing value is valid; "no end user" alone is never a
  finding.
- **provenance**: ADO ids are authoring-time references (D9); stable key is
  the scenario slug.

## clean

- provenance: T5 id 42 (authoring-time reference, D9)
- mirror of: clean (T1 id 5) — invoice PDF in confirmation email
- framing: As the order service team, we need an invoice-rendering component
  fed by the existing order data, so that order confirmations can carry a
  formal invoice PDF without new order-domain work.
- facts:
  - customers currently receive a plain-text order confirmation with no price breakdown
  - the order service already returns complete invoice data via `GET /orders/{id}`: line items, unit prices, VAT rates, totals
  - order data is complete, so the work is a rendering component + email attachment, not order-domain changes
  - top request from B2B account managers this quarter; B2B customers and expense claims require a formal invoice document
  - scope: the rendering component and the email-sending change; out of scope: credit notes, self-service invoice re-download from the account page
- criteria:
  - order payment succeeded → confirmation email job sends the email within 2 minutes with the invoice PDF attached
  - invoice PDF rendered from the order API response → line items with unit prices, per-item VAT rate, and gross total match `GET /orders/{id}` exactly
  - hard-bouncing recipient address → email retried once after 5 minutes, then written to the mail audit log (no silent loss)
  - invoice rendering failure → email still sent without the attachment; failure on the alerting dashboard; no customer-visible error
- must-not-add: no facts, dependencies, links, deadlines, or sign-off beyond the above.
- expected verdict: clean acceptance — no findings required.

## business-weak

- provenance: T5 id 43 (authoring-time reference, D9)
- mirror of: business-weak (T1 id 10) — Google Pay at checkout
- framing: As the engineering team, we need to wire the PSP's `google_pay`
  method into the existing checkout payment list, so that checkout supports
  more payment options.
- facts:
  - the PSP exposes Google Pay in its gateway API (`POST /payment-intents`, method `google_pay`)
  - the web checkout can render the button via the PSP's JS SDK
  - the checkout payment-list flow is the existing integration point
  - justification: competitors have it and customers keep asking for more payment options at checkout
  - scope: add the method to the existing checkout payment-list flow; out of scope: other payment methods, native apps
- criteria:
  - PSP SDK reports Google Pay availability in a browser → button shown when the payment step renders; hidden otherwise
  - customer selects Google Pay → payment intent created with method `google_pay`; existing payment flow completes; order state machine unchanged
  - failed or cancelled intent → flow returns to the payment-list step, previous selection cleared, no order state change, failure logged with the PSP correlation ID
  - method enabled → checkout e2e suite and accessibility checks pass; button keyboard-accessible
- must-not-add: **no target segment, no measurable success criterion, no
  quantified demand, no priority rationale, and no technical-effort
  justification standing in for business value** — the weak case is the seed
  and must stay vague (the PO supplies it at review time per the manual plan).
- expected verdict: business findings on the vague value case (as in the
  manual plan); engineering side is solid; "no end user" is not a finding.

## engineering-weak

- provenance: T5 id 44 (authoring-time reference, D9)
- mirror of: engineering-weak (T1 id 14) — automatic payment retry on PSP failure
- framing: As the payments service, we need automatic retry for PSP errors,
  so that transient PSP failures stop failing orders outright.
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
- expected verdict: engineering findings on the unspecified retry policy; business value is well quantified.

## conflicting

- provenance: T5 id 45 (authoring-time reference, D9)
- mirror of: conflicting (T1 id 17) — auto-select last used payment method
- framing: As the checkout service, we need to pre-select and charge the
  returning customer's last used payment method, so that the one-page
  checkout redesign can remove the payment selection step.
- facts:
  - checkout currently shows all available payment methods with no default; returning customers re-pick their method on every order
  - the one-page checkout redesign under this feature aims to remove checkout steps
  - funnel analytics: returning customers spend a median 11 seconds selecting a payment method they used on the previous order
  - UX research flagged method selection as the top friction point for returning customers; marketing asked for a "one-tap pay" experience
  - scope: web checkout for signed-in returning customers; out of scope: guest checkout, native apps, adding new payment methods
- criteria:
  - returning customer with a previously used method, checkout loads → last used method pre-selected
  - pre-selected method, customer confirms the order → payment charged with that method **without a separate selection step**
  - last used method no longer available, checkout loads → no method pre-selected; message explains why
- must-not-add: **no explicit confirmation action, no visible Pay button, no
  method-change mechanism, no "pre-selected method and total shown"
  criterion** — the unmitigated charge-without-selection-step (business risk)
  vs the step-removal requirement (engineering constraint) is the planted
  conflict; the PO resolves it at review time per the manual plan.
- expected verdict: same conflict surfaced and resolved via PO dialogue (as
  in the manual plan).

## partial-resolution

- provenance: T5 id 46 (authoring-time reference, D9)
- mirror of: partial-resolution (T1 id 18) — save payment details for returning customers
- framing: As the payments team, we need to store payment details for
  returning customers, so that checkout no longer requires re-entering card
  data.
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
- expected verdict: same B-1/B-2/E-1/E-2 gap arc, resolved through PO dialogue.

## unresolvable

- provenance: T5 id 47 (authoring-time reference, D9)
- mirror of: unresolvable (T1 id 19) — localize checkout for international customers
- framing: As the platform team, we need checkout to support additional
  markets, languages, and currencies, so that international expansion is not
  blocked by checkout.
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
- expected verdict: parked at the loop safety cap (unresolvable).

## hidden-conflict

- provenance: T5 id 48 (authoring-time reference, D9)
- mirror of: hidden-conflict (T1 id 20) — 30-minute order edit window after purchase
- framing: As the order service, we need an in-place order edit window after
  purchase, so that customers can fix address, size, and quantity mistakes
  without cancel-and-reorder.
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
  model; no refund fees, re-authorization, or edit-count limits**; both
  reviews must be individually positive — the contradiction is only visible
  to synthesis.
- expected verdict: both perspectives individually positive; synthesis flags
  the capture-model contradiction (zero per-perspective findings).
