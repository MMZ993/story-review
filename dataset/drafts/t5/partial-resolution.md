# partial-resolution — T5 draft

Title: Saved payment details

Description:
As the payments team, we need to store payment details for returning customers, so that checkout no longer requires re-entering card data.

Returning customers re-enter full card details on every order; checkout for returning customers averages 2m40s; no payment data is stored today. The Q4 growth goal is +15% conversion for returning customers. Payment-data entry is the 3rd-highest drop-off point in funnel analytics.

Scope is web checkout, cards via the current PSP. Out of scope are native apps, wallets, and bank transfers.

Acceptance Criteria field:
- Returning customer with saved payment details reaches checkout → saved method available for selection without re-entering card details.
- Customer opts to save payment details, payment completes → details stored for future checkouts.
- Saved method used at checkout, payment completes → customer reaches the confirmation page.

## Self-check

Every fact and criterion is present. Nothing has been added. The consent/retention, tokenization/PCI-DSS/raw-storage, expired/removed-card, and measurable-faster-checkout gaps are preserved; no dependencies, links, deadlines, contacts, or sign-off are supplied.
