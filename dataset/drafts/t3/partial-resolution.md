# partial-resolution — T3 draft

## T3 rendering

Title: Save payment details for returning customers

Description:
When returning customers reach checkout and must re-enter full card details, I want saved payment details to be available for selection, so I can support the Q4 growth goal of +15% conversion for returning customers.

Returning customers re-enter full card details on every order; checkout for returning customers averages 2m40s; no payment data is stored today. Payment-data entry is the 3rd-highest drop-off point in funnel analytics.

Scope is web checkout and cards via the current PSP. Out of scope are native apps, wallets, and bank transfers.

Acceptance Criteria field:
- When a returning customer with saved payment details reaches checkout, the saved method is available for selection without re-entering card details.
- When a customer opts to save payment details and payment completes, the details are stored for future checkouts.
- When a saved method is used at checkout and payment completes, the customer reaches the confirmation page.

## Self-check

Every canonical fact and criterion is present. No consent or retention policy, tokenization, PCI-DSS or raw-storage handling, expired/removed-card behavior, or measurable faster-checkout criterion has been added. The framing states the actual returning-customer and conversion intent.
