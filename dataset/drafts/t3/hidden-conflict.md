# hidden-conflict — T3 draft

## T3 rendering

Title: 30-minute order edit window after purchase

Description:
When customers need to change an address, size, or quantity after checkout completes, I want a 30-minute in-place order edit window, so I can reduce avoidable support contacts and prevent cancel-and-reorder losses.

Customers cannot modify an order (address, size, quantity) after checkout completes; the only path today is cancel-and-reorder or a support ticket. The order pipeline captures payment immediately at order placement. Support handles ~90 order-change tickets per week; cancel-and-reorder loses a share of those orders entirely. This is a CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%. Payment handling carries no cost: the customer's payment is only reserved during the day, so releasing the reservation is free.

Scope is edits to shipping address and item size/quantity. Out of scope are changing the payment method, subscription orders, and native apps.

Acceptance Criteria field:
- When a completed order has an edit requested within 30 minutes, update the order in place with no new order created.
- When an edit changes the order total, automatically charge or refund the difference.
- When an edit is requested after the 30-minute window, tell the customer to contact support.

## Self-check

Every canonical fact and criterion is present. Both contradictory payment-capture statements survive unreconciled. Nothing clarifies or reconciles the payment-capture model; no refund fees, re-authorization, or edit-count limits have been added. The framing reflects the order-edit and support-contact intent.
