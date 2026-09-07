# clean — T6 draft

## Invoice mail

Customers currently get a plain-text order confirmation with no price breakdown. The order service already gives complete invoice data through `GET /orders/{id}`: line items, unit prices, VAT rates, totals. B2B customers and expense claims need a formal invoice document, and it is the top request from B2B account managers this quarter. The order data is complete, so this is rendering + attachment only: invoice rendering and email attachment, not credit notes or self-service invoice re-download from the account page.

After order payment succeeded, the confirmation email job sends the email within 2 minutes with the invoice PDF attached. Render the invoice PDF from the order API response so its line items with unit prices, per-item VAT rate, and gross total match `GET /orders/{id}` exactly. If the recipient address hard-bounces, retry the email once after 5 minutes, then write it to the mail audit log, with no silent loss. If invoice rendering fails, still send the email without the attachment, put the failure on the alerting dashboard, and show no customer-visible error.

## Self-check

Every canonical fact and criterion is present in prose. Nothing was added. No planted flaw exists to preserve.
