# conflicting — T2 draft (from T1 id 17)

## Must-retain facts

- Checkout currently shows all available payment methods with no default.
- Returning customers re-pick their method on every order.
- The one-page checkout redesign under this feature aims to remove checkout steps.
- Funnel analytics show returning customers spend a median 11 seconds selecting a payment method used on their previous order.
- UX research flagged method selection as the top friction point for returning customers.
- Marketing asked for a "one-tap pay" experience.
- Scope is web checkout for signed-in returning customers.
- Out of scope: guest checkout, native apps, and adding new payment methods.
- When a returning customer with a previously used payment method loads checkout, their last used method is pre-selected.
- When a customer confirms an order with a pre-selected method, payment is charged with that method without a separate selection step.
- When a customer's last used method is no longer available and checkout loads, no method is pre-selected and a message explains why.

## Must-not-add

- Do not add an explicit confirmation action, a visible Pay button, a one-tap method-change mechanism, or a criterion showing the pre-selected method and total.
- Do not resolve or clarify the tension between removing checkout steps and charging without a separate selection step.
- Do not add facts, dependencies, links, deadlines, contacts, or sign-off not present in T1.

## T2 rendering

**Title:** Auto-select last used payment method at checkout

**Description:** Checkout currently shows all available payment methods with no default, so returning customers re-pick their method on every order. The one-page checkout redesign under this feature aims to remove checkout steps.

**Reason:** Funnel analytics show returning customers spend a median 11 seconds selecting a payment method used on their previous order. UX research flagged method selection as the top friction point for returning customers. Marketing asked for a "one-tap pay" experience.

**Implementation:** Apply this to web checkout for signed-in returning customers. Guest checkout, native apps, and adding new payment methods are out of scope.

**For this story:**

1. Verify that checkout pre-selects the last used method for a returning customer with a previously used payment method.
2. Verify that, when the customer confirms the order with a pre-selected method, payment is charged with that method without a separate selection step.
3. Verify that checkout pre-selects no method and displays a message explaining why when the customer's last used method is no longer available.

---

**Acceptance Criteria field:** empty.

## Self-check

- Every must-retain fact is present.
- Nothing beyond the T1 facts was added.
- The conflicting confirmation/checkout-step gap remains unresolved.
- The Acceptance Criteria field is empty.
