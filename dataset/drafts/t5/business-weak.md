# business-weak — T5 draft

Title: Google Pay checkout integration

Description:
As the engineering team, we need to wire the PSP's `google_pay` method into the existing checkout payment list, so that checkout supports more payment options.

The PSP exposes Google Pay in its gateway API (`POST /payment-intents`, method `google_pay`). The web checkout can render the button via the PSP's JS SDK, and the checkout payment-list flow is the existing integration point. Competitors have it and customers keep asking for more payment options at checkout.

Scope is adding the method to the existing checkout payment-list flow. Out of scope are other payment methods and native apps.

Acceptance Criteria field:
- PSP SDK reports Google Pay availability in a browser → button shown when the payment step renders; hidden otherwise.
- Customer selects Google Pay → payment intent created with method `google_pay`; existing payment flow completes; order state machine unchanged.
- Failed or cancelled intent → flow returns to the payment-list step, previous selection cleared, no order state change, failure logged with the PSP correlation ID.
- Method enabled → checkout e2e suite and accessibility checks pass; button keyboard-accessible.

## Self-check

Every fact and criterion is present. Nothing has been added. The vague business-value flaw is preserved: no target segment, measurable success criterion, quantified demand, priority rationale, or technical-effort justification standing in for business value; no dependencies, links, deadlines, contacts, or sign-off are supplied.
