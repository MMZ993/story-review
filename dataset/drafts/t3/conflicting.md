# conflicting — T3 draft

## T3 rendering

Title: Auto-select last used payment method at checkout

Description:
When a signed-in returning customer reaches web checkout, I want their last used payment method pre-selected without a separate selection step, so I can remove checkout steps and provide the requested one-tap pay experience.

Checkout currently shows all available payment methods with no default; returning customers re-pick their method on every order. The one-page checkout redesign under this feature aims to remove checkout steps. Funnel analytics show that returning customers spend a median 11 seconds selecting a payment method they used on the previous order. UX research flagged method selection as the top friction point for returning customers, and marketing asked for a "one-tap pay" experience.

Scope is web checkout for signed-in returning customers. Out of scope are guest checkout, native apps, and adding new payment methods.

Acceptance Criteria field:
- When a returning customer with a previously used method loads checkout, the last used method is pre-selected.
- When the pre-selected method is present and the customer confirms the order, payment is charged with that method without a separate selection step.
- When the last used method is no longer available and checkout loads, no method is pre-selected and a message explains why.

## Self-check

Every canonical fact and criterion is present. No explicit confirmation action, visible Pay button, method-change mechanism, or "pre-selected method and total shown" criterion has been added. The framing preserves the unreconciled no-separate-selection-step intent.
