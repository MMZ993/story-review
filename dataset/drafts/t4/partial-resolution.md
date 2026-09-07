# partial-resolution — T4 draft

## T4 rendering

**Title:** As a returning customer, I want to save payment details so that I do not re-enter full card details on every order.

**Description:**

Returning customers re-enter full card details on every order. Checkout for returning customers averages 2m40s, and no payment data is stored today. The Q4 growth goal is +15% conversion for returning customers, and payment-data entry is the 3rd-highest drop-off point in funnel analytics.

Scope is web checkout and cards via the current PSP. Native apps, wallets, and bank transfers are out of scope.

**Acceptance Criteria field:**

- When a returning customer with saved payment details reaches checkout, the saved method is available for selection without re-entering card details.
- When a customer opts to save payment details and payment completes, the details are stored for future checkouts.
- When a saved method is used at checkout and payment completes, the customer reaches the confirmation page.

## Self-check

- Every canonical fact and criterion is present; nothing beyond them is added.
- No consent or retention policy, tokenization, PCI-DSS or raw-storage handling, expired/removed-card behavior, or measurable faster-checkout criterion is supplied.
- The title's returning customer, saved payment details, and no-re-entry benefit also appear in the body.
