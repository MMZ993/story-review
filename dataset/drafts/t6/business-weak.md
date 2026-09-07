# business-weak — T6 draft

## GP

The PSP exposes Google Pay in its gateway API, `POST /payment-intents`, with method `google_pay`, and web checkout can render the button through the PSP's JS SDK. Use the existing checkout payment-list flow for it. Competitors have it and customers keep asking for more payment options at checkout. Add the method to that existing checkout payment-list flow, not other payment methods or native apps.

When the PSP SDK reports Google Pay availability in a browser, show the button when the payment step renders, otherwise hide it. When a customer selects Google Pay, create the payment intent with method `google_pay`, let the existing payment flow complete, and leave the order state machine unchanged. A failed or cancelled intent goes back to the payment-list step with the previous selection cleared, no order state change, and the failure logged with the PSP correlation ID. Once the method is enabled, the checkout e2e suite and accessibility checks pass and the button is keyboard-accessible.

## Self-check

Every canonical fact and criterion is present in prose. Nothing was added. The vague business value is preserved without a target segment, measurable success criterion, quantified demand, or priority rationale.
