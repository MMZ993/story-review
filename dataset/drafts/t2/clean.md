# clean — T2 draft (from T1 id 5)

## Must-retain facts

- Customers currently receive a plain-text order confirmation with no price breakdown.
- The order service already returns complete invoice data through `GET /orders/{id}`: line items, unit prices, VAT rates, and totals.
- B2B customers and expense claims require a formal invoice document.
- This is the top request from B2B account managers this quarter.
- Because order data is complete, the work is rendering plus attachment only.
- Scope adds invoice rendering and email attachment.
- Out of scope: credit notes and self-service invoice re-download from the account page.
- For an order whose payment succeeded, when the confirmation email job runs, the email is sent within 2 minutes with the invoice PDF attached.
- When the invoice PDF is rendered from the order API response, its line items with unit prices, per-item VAT rate, and gross total match `GET /orders/{id}` exactly.
- For a hard-bouncing recipient address, sending the confirmation email retries once after 5 minutes and then writes to the mail audit log, with no silent loss.
- For an invoice rendering failure, the confirmation email job still sends the email without the attachment and the failure appears on the alerting dashboard, with no customer-visible error.

## Must-not-add

- No facts, dependencies, links, deadlines, contacts, or sign-off not present in T1.

## T2 rendering

**Title:** Invoice PDF in order confirmation email

**Description:** Customers currently receive a plain-text order confirmation with no price breakdown. The order service already returns complete invoice data through `GET /orders/{id}`: line items, unit prices, VAT rates, and totals.

**Reason:** B2B customers and expense claims require a formal invoice document. This is the top request from B2B account managers this quarter.

**Implementation:** Add invoice rendering and email attachment. Order data is complete, so this is rendering plus attachment only. Credit notes and self-service invoice re-download from the account page are out of scope.

**For this story:**

1. Verify that, for an order whose payment succeeded, the confirmation email job sends the email within 2 minutes with the invoice PDF attached.
2. Verify that an invoice PDF rendered from the order API response has line items with unit prices, per-item VAT rate, and gross total that match `GET /orders/{id}` exactly.
3. Verify that a hard-bouncing recipient address causes the confirmation email to retry once after 5 minutes and then be written to the mail audit log, with no silent loss.
4. Verify that an invoice rendering failure still sends the email without the attachment and appears on the alerting dashboard, with no customer-visible error.

---

**Acceptance Criteria field:** empty.

## Self-check

- Every must-retain fact is present.
- Nothing beyond the T1 facts was added.
- No quality gaps were repaired or introduced.
- The Acceptance Criteria field is empty.
