# clean — T5 draft

Title: Invoice confirmation renderer

Description:
As the order service team, we need an invoice-rendering component fed by the existing order data, so that order confirmations can carry a formal invoice PDF without new order-domain work.

Customers currently receive a plain-text order confirmation with no price breakdown. The order service already returns complete invoice data via `GET /orders/{id}`: line items, unit prices, VAT rates, totals. Order data is complete, so the work is a rendering component + email attachment, not order-domain changes. This is the top request from B2B account managers this quarter; B2B customers and expense claims require a formal invoice document.

Scope is the rendering component and the email-sending change. Out of scope are credit notes and self-service invoice re-download from the account page.

Acceptance Criteria field:
- Order payment succeeded → confirmation email job sends the email within 2 minutes with the invoice PDF attached.
- Invoice PDF rendered from the order API response → line items with unit prices, per-item VAT rate, and gross total match `GET /orders/{id}` exactly.
- Hard-bouncing recipient address → email retried once after 5 minutes, then written to the mail audit log (no silent loss).
- Invoice rendering failure → email still sent without the attachment; failure on the alerting dashboard; no customer-visible error.

## Self-check

Every fact and criterion is present. Nothing has been added. The clean scenario remains free of a planted flaw, with no dependencies, links, deadlines, contacts, or sign-off.
