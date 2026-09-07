# hidden-conflict — T5 draft

Title: Post-purchase order edit window

Description:
As the order service, we need an in-place order edit window after purchase, so that customers can fix address, size, and quantity mistakes without cancel-and-reorder.

Customers cannot modify an order (address, size, quantity) after checkout completes; the only path today is cancel-and-reorder or a support ticket. The order pipeline captures payment immediately at order placement. Support handles ~90 order-change tickets per week; cancel-and-reorder loses a share of those orders entirely. This is a CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%. Payment handling carries no cost: the customer's payment is only reserved during the day, so releasing the reservation is free.

Scope is edits to shipping address and item size/quantity. Out of scope are changing the payment method, subscription orders, and native apps.

Acceptance Criteria field:
- Completed order, edit requested within 30 minutes → order updated in place, no new order created.
- Edit changes the order total → customer automatically charged or refunded the difference.
- Edit requested after the 30-minute window → customer told to contact support.

## Self-check

Every fact and criterion is present. Nothing has been added. Both contradictory payment-capture statements remain unreconciled; no refund fees, re-authorization, or edit-count limits are supplied. The hidden conflict is preserved as specified, with no dependencies, links, deadlines, contacts, or sign-off.
