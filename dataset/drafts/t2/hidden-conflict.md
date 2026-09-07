# hidden-conflict — T2 draft (from T1 id 20)

## Must-retain facts

- Customers cannot modify an order's address, size, or quantity after checkout completes.
- The only current path is cancel-and-reorder or a support ticket.
- The order pipeline captures payment immediately at order placement.
- Support handles ~90 order-change tickets per week.
- Cancel-and-reorder loses a share of those orders entirely.
- This is a CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%.
- Payment handling carries no cost because the customer's payment is only reserved during the day, so releasing the reservation is free.
- Scope includes edits to shipping address and item size/quantity.
- Out of scope: changing the payment method, subscription orders, and native apps.
- When a customer requests an edit within 30 minutes for a completed order, the order is updated in place without a new order being created.
- When an edit changes the order total and the edit is applied, the customer is automatically charged or refunded the difference.
- When a customer requests an edit after the 30-minute window has elapsed, the customer is told to contact support.

## Must-not-add

- Both contradictory payment-capture statements must survive: payment captures immediately at order placement, and payment is only reserved during the day so releasing the reservation is free.
- Do not clarify which payment-capture statement is true or reconcile the two models.
- Do not add refund fees, re-authorization, a one-edit limit, or any other later PO resolution.
- Do not add facts, dependencies, links, deadlines, contacts, or sign-off not present in T1.

## T2 rendering

**Title:** 30-minute order edit window after purchase

**Description:** Customers cannot modify an order's address, size, or quantity after checkout completes; the only path today is cancel-and-reorder or a support ticket. The order pipeline captures payment immediately at order placement. Support handles ~90 order-change tickets per week, and cancel-and-reorder loses a share of those orders entirely.

**Reason:** This is a CX roadmap item under the Q4 goal of cutting avoidable support contacts by 20%. Payment handling carries no cost: the customer's payment is only reserved during the day, so releasing the reservation is free.

**Implementation:** Support edits to shipping address and item size/quantity. Changing the payment method, subscription orders, and native apps are out of scope.

**For this story:**

1. Verify that a completed order is updated in place without a new order being created when the customer requests an edit within 30 minutes.
2. Verify that the customer is automatically charged or refunded the difference when an applied edit changes the order total.
3. Verify that a customer requesting an edit after the 30-minute window has elapsed is told to contact support.

---

**Acceptance Criteria field:** empty.

## Self-check

- Every must-retain fact is present.
- Nothing beyond the T1 facts was added.
- Both contradictory payment-capture statements remain unclarified.
- The Acceptance Criteria field is empty.
