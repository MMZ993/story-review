# business-weak — T2 draft (from T1 id 10)

## Must-retain facts

- The payment service provider exposes Google Pay in its gateway API: `POST /payment-intents` with method `"google_pay"`.
- The web checkout can render the button through the PSP's JS SDK.
- The checkout payment-list flow is the existing integration point.
- Competitors have Google Pay and customers keep asking for more payment options at checkout.
- Scope adds the method to the existing checkout payment-list flow.
- Out of scope: other payment methods and native apps.
- When the PSP SDK reports Google Pay availability in a browser and the checkout payment step renders, the Google Pay button is shown; otherwise it is hidden.
- When a customer selects Google Pay and payment is initiated, a payment intent with method `google_pay` is created and the existing payment flow completes with the order state machine unchanged.
- When a Google Pay intent fails or is cancelled, the flow returns to the payment-list step with the previous selection cleared, no order state change, and the failure logged with the PSP correlation ID.
- With the method enabled, the checkout e2e suite and accessibility checks pass with the button keyboard-accessible.

## Must-not-add

- Do not add a target segment.
- Do not add a measurable success criterion, quantified demand, or priority rationale.
- Do not fix the vague business justification that competitors have it and customers ask for more options.
- Do not add facts, dependencies, links, deadlines, contacts, or sign-off not present in T1.

## T2 rendering

**Title:** Google Pay at checkout

**Description:** The payment service provider exposes Google Pay in its gateway API through `POST /payment-intents` with method `"google_pay"`. The web checkout can render the button through the PSP's JS SDK. The checkout payment-list flow is the existing integration point.

**Reason:** Competitors have it and customers keep asking for more payment options at checkout.

**Implementation:** Add the method to the existing checkout payment-list flow. Other payment methods and native apps are out of scope.

**For this story:**

1. Verify that the Google Pay button is shown when the PSP SDK reports Google Pay availability in a browser as the checkout payment step renders, and hidden otherwise.
2. Verify that selecting Google Pay and initiating payment creates a payment intent with method `google_pay` and completes the existing payment flow with the order state machine unchanged.
3. Verify that a failed or cancelled Google Pay intent returns the flow to the payment-list step with the previous selection cleared, no order state change, and the failure logged with the PSP correlation ID.
4. Verify that, with the method enabled, the checkout e2e suite and accessibility checks pass and the button is keyboard-accessible.

---

**Acceptance Criteria field:** empty.

## Self-check

- Every must-retain fact is present.
- Nothing beyond the T1 facts was added.
- The missing target segment, success metric, quantified demand, and priority rationale remain missing.
- The Acceptance Criteria field is empty.
