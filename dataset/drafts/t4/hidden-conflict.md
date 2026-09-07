# hidden-conflict — T4 draft

## T4 rendering

**Title:** As a customer, I want a 30-minute order edit window after purchase so that I can modify my order after checkout completes.

**Description:**

Customers cannot modify an order's address, size, or quantity after checkout completes; the only path today is cancel-and-reorder or a support ticket. The order pipeline captures payment immediately at order placement. Support handles ~90 order-change tickets per week, and cancel-and-reorder loses a share of those orders entirely. This is a CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%.

Payment handling carries no cost: the customer's payment is only reserved during the day, so releasing the reservation is free. Scope is edits to shipping address and item size/quantity; changing the payment method, subscription orders, and native apps are out of scope.

**Acceptance Criteria field:**

- When an edit is requested within 30 minutes for a completed order, the order is updated in place and no new order is created.
- If an edit changes the order total, the customer is automatically charged or refunded the difference.
- When an edit is requested after the 30-minute window, the customer is told to contact support.

## Self-check

- Every canonical fact and criterion is present; nothing beyond them is added.
- Both unreconciled payment-capture statements survive: payment is captured immediately at order placement, and payment is only reserved during the day so releasing the reservation is free.
- No clarification or reconciliation of the payment-capture model, refund fees, re-authorization, or edit-count limit is supplied.
- The title's customer, 30-minute post-purchase edit window, and order-modification benefit also appear in the body.
