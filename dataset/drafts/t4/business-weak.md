# business-weak — T4 draft

## T4 rendering

**Title:** As a customer, I want Google Pay at checkout so that I have another payment option at checkout.

**Description:**

The PSP exposes Google Pay in its gateway API through `POST /payment-intents` with method `google_pay`, and the web checkout can render the button through the PSP's JS SDK. The existing checkout payment-list flow is the integration point.

Competitors have it and customers keep asking for more payment options at checkout. Scope is adding the method to the existing checkout payment-list flow; other payment methods and native apps are out of scope.

**Acceptance Criteria field:**

- If the PSP SDK reports Google Pay availability in a browser, the button is shown when the payment step renders; otherwise it is hidden.
- When a customer selects Google Pay, a payment intent is created with method `google_pay`, the existing payment flow completes, and the order state machine is unchanged.
- If an intent fails or is cancelled, the flow returns to the payment-list step, the previous selection is cleared, there is no order state change, and the failure is logged with the PSP correlation ID.
- When the method is enabled, the checkout e2e suite and accessibility checks pass, and the button is keyboard-accessible.

## Self-check

- Every canonical fact and criterion is present; nothing beyond them is added.
- No target segment, measurable success criterion, quantified demand, or priority rationale is supplied.
- The title's customer, Google Pay at checkout, and additional-payment-option benefit also appear in the body.
