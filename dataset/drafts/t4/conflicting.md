# conflicting — T4 draft

## T4 rendering

**Title:** As a signed-in returning customer, I want my last used payment method auto-selected at web checkout so that I do not re-pick it on every order.

**Description:**

Checkout currently shows all available payment methods with no default, so returning customers re-pick their method on every order. The one-page checkout redesign under this feature aims to remove checkout steps. Funnel analytics show that returning customers spend a median 11 seconds selecting a payment method they used on the previous order. UX research flagged method selection as the top friction point for returning customers, and marketing asked for a "one-tap pay" experience.

Scope is web checkout for signed-in returning customers. Guest checkout, native apps, and adding new payment methods are out of scope.

**Acceptance Criteria field:**

- When a returning customer with a previously used method loads checkout, the last used method is pre-selected.
- When the pre-selected method is present and the customer confirms the order, payment is charged with that method without a separate selection step.
- When the last used method is no longer available and checkout loads, no method is pre-selected and a message explains why.

## Self-check

- Every canonical fact and criterion is present; nothing beyond them is added.
- No explicit confirmation action, visible Pay button, method-change mechanism, or criterion that the pre-selected method and total are shown is supplied.
- The title's signed-in returning customer, web-checkout auto-selection, and no-re-picking benefit also appear in the body.
