# partial-resolution — T2 draft (from T1 id 18)

## Must-retain facts

- Returning customers re-enter full card details on every order.
- Checkout for returning customers averages 2m40s.
- No payment data is stored today.
- The Q4 growth goal is +15% conversion for returning customers.
- Payment-data entry is the 3rd-highest drop-off point in funnel analytics.
- Scope is web checkout and cards via the current PSP.
- Out of scope: native apps, wallets, and bank transfers.
- When a returning customer with saved payment details reaches checkout, their saved method is available for selection without re-entering card details.
- When a customer opts to save payment details and payment completes, the details are stored for future checkouts.
- When a saved method is used at checkout and payment completes, the customer reaches the confirmation page.

## Must-not-add

- Do not add a consent or retention policy.
- Do not add tokenization, a prohibition on raw card storage, or PCI-DSS handling.
- Do not add expired- or removed-card behavior.
- Do not turn the Q4 +15% conversion goal or faster checkout into a measurable acceptance criterion.
- Do not add facts, dependencies, links, deadlines, contacts, or sign-off not present in T1.

## T2 rendering

**Title:** Save payment details for returning customers

**Description:** Returning customers re-enter full card details on every order. Checkout for returning customers averages 2m40s, and no payment data is stored today.

**Reason:** The Q4 growth goal is +15% conversion for returning customers. Payment-data entry is the 3rd-highest drop-off point in funnel analytics.

**Implementation:** Support web checkout and cards via the current PSP. Native apps, wallets, and bank transfers are out of scope.

**For this story:**

1. Verify that a returning customer with saved payment details has their saved method available for selection at checkout without re-entering card details.
2. Verify that payment details are stored for future checkouts when a customer opts to save payment details and payment completes.
3. Verify that a customer reaches the confirmation page when a saved method is used at checkout and payment completes.

---

**Acceptance Criteria field:** empty.

## Self-check

- Every must-retain fact is present.
- Nothing beyond the T1 facts was added.
- Consent, retention, tokenization, PCI-DSS, expired-card behavior, and measurable checkout-speed criterion remain absent.
- The Acceptance Criteria field is empty.
