# hidden-conflict — T6 draft

## 30m edit

Customers cannot modify an order's address, size, or quantity after checkout completes; today the only route is cancel-and-reorder or a support ticket. The order pipeline captures payment immediately at order placement. Support handles ~90 order-change tickets per week, and cancel-and-reorder loses a share of those orders entirely. This is a CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%. Payment handling carries no cost: the customer's payment is only reserved during the day, so releasing the reservation is free. Cover edits to shipping address and item size/quantity, not changing the payment method, subscription orders, or native apps.

For a completed order with an edit requested within 30 minutes, update the order in place with no new order created. If the edit changes the order total, automatically charge or refund the difference. For an edit requested after the 30-minute window, tell the customer to contact support.

## Self-check

Every canonical fact and criterion is present in prose. Nothing was added. Both contradictory payment-capture statements remain unreconciled, with no refund fees, re-authorization, or edit-count limits.
