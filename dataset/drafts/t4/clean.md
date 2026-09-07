# clean — T4 draft

## T4 rendering

**Title:** As a customer, I want an invoice PDF in my order confirmation email so that I have a formal invoice document for B2B and expense claims.

**Description:**

Customers currently receive a plain-text order confirmation with no price breakdown. B2B customers and expense claims require a formal invoice document, and this is the top request from B2B account managers this quarter.

The order service already returns complete invoice data through `GET /orders/{id}`: line items, unit prices, VAT rates, and totals. Order data is complete, so the work is rendering and attachment only. The scope is invoice rendering and email attachment; credit notes and self-service invoice re-download from the account page are out of scope.

**Acceptance Criteria field:**

- When order payment succeeds, the confirmation email job sends the email within 2 minutes with the invoice PDF attached.
- An invoice PDF rendered from the order API response has line items with unit prices, per-item VAT rate, and gross total that match `GET /orders/{id}` exactly.
- For a hard-bouncing recipient address, the email is retried once after 5 minutes and then written to the mail audit log, with no silent loss.
- If invoice rendering fails, the email is still sent without the attachment, the failure appears on the alerting dashboard, and there is no customer-visible error.

## Self-check

- Every canonical fact and criterion is present; nothing beyond them is added.
- The scope exclusions for credit notes and self-service invoice re-download are preserved.
- The title's customer, invoice PDF in the confirmation email, and formal-invoice benefit also appear in the body.
