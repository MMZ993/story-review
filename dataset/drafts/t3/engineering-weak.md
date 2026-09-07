# engineering-weak — T3 draft

## T3 rendering

Title: Automatic payment retry on PSP failure

Description:
When a temporary PSP outage causes a payment to fail outright, I want to retry PSP errors automatically, so I can reduce abandoned carts and payment-failure support tickets.

A temporary PSP outage (timeout, 5xx) fails the order outright today: the customer sees an error, the cart is abandoned, and support tickets follow. The order service already distinguishes PSP decline from PSP error, so a legitimate retry is identifiable. Payment errors were 38% of abandoned carts last quarter; the payments team estimates roughly a fifth are transient PSP failures. Support receives ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month.

Scope is automatic retry for PSP errors only. Out of scope are retries for declines, changes to the decline messaging, and native apps.

Acceptance Criteria field:
- When payment failed due to PSP error (not decline), the system retries automatically without customer action.
- When a retried payment succeeds, or failure is a decline, retries stop immediately.
- When retries are exhausted and the last attempt fails, the customer sees the standard payment-failed page and the order remains recoverable from the cart.
- When any retried payment completes, whether success or final failure, the retry outcome is visible in the existing payments dashboard.

## Self-check

Every canonical fact and criterion is present. No retry-policy specifics, idempotency guarantee, or cart/order-hold behavior during retries has been added. The framing reflects automatic retry for identifiable PSP errors.
