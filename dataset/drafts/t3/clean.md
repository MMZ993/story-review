# clean — T3 draft

## T3 rendering

Title: Invoice PDF in order confirmation email

Description:
When customers need a formal invoice with their order confirmation, I want to render and attach an invoice PDF from complete order data, so I can support B2B customers and expense claims.

Customers currently receive a plain-text order confirmation with no price breakdown. The order service already returns complete invoice data via `GET /orders/{id}`: line items, unit prices, VAT rates, totals. B2B customers and expense claims require a formal invoice document, and this is the top request from B2B account managers this quarter. Order data is complete, so the work is rendering + attachment only.

Scope is invoice rendering and email attachment. Out of scope are credit notes and self-service invoice re-download from the account page.

Acceptance Criteria field:
- When order payment succeeded, the confirmation email job sends the email within 2 minutes with the invoice PDF attached.
- When the invoice PDF is rendered from the order API response, line items with unit prices, per-item VAT rate, and gross total match `GET /orders/{id}` exactly.
- For a hard-bouncing recipient address, retry the email once after 5 minutes, then write it to the mail audit log with no silent loss.
- If invoice rendering fails, still send the email without the attachment; put the failure on the alerting dashboard with no customer-visible error.

## Self-check

Every canonical fact and criterion is present. Nothing has been added; no dependencies, links, deadlines, contacts, or sign-off are supplied. The framing states the actual invoice-rendering and attachment intent.
