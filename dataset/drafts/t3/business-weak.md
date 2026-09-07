# business-weak — T3 draft

## T3 rendering

Title: Google Pay at checkout

Description:
When customers want more payment options at checkout, I want to add Google Pay to the existing checkout payment-list flow, so I can offer the method competitors have and customers keep asking for.

The PSP exposes Google Pay in its gateway API (`POST /payment-intents`, method `google_pay`), and the web checkout can render the button via the PSP's JS SDK. The checkout payment-list flow is the existing integration point. Competitors have it and customers keep asking for more payment options at checkout.

Scope is adding the method to the existing checkout payment-list flow. Out of scope are other payment methods and native apps.

Acceptance Criteria field:
- When the PSP SDK reports Google Pay availability in a browser, show the button when the payment step renders; hide it otherwise.
- When a customer selects Google Pay, create a payment intent with method `google_pay`; complete the existing payment flow and leave the order state machine unchanged.
- For a failed or cancelled intent, return the flow to the payment-list step, clear the previous selection, make no order state change, and log the failure with the PSP correlation ID.
- When the method is enabled, the checkout e2e suite and accessibility checks pass, and the button is keyboard-accessible.

## Self-check

Every canonical fact and criterion is present. No target segment, measurable success criterion, quantified demand, or priority rationale has been added. The framing expresses the stated, deliberately vague payment-option intent.
