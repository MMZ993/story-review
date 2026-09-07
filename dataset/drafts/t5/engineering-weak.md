# engineering-weak — T5 draft

Title: PSP error retry

Description:
As the payments service, we need automatic retry for PSP errors, so that transient PSP failures stop failing orders outright.

A temporary PSP outage (timeout, 5xx) fails the order outright today: customer sees an error, cart abandoned, support tickets follow. The order service already distinguishes PSP decline from PSP error, so a legitimate retry is identifiable. Payment errors were 38% of abandoned carts last quarter; the payments team estimates roughly a fifth are transient PSP failures. Support receives ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month.

Scope is automatic retry for PSP errors only. Out of scope are retries for declines, changes to the decline messaging, and native apps.

Acceptance Criteria field:
- Payment failed due to PSP error (not decline) → system retries automatically without customer action.
- Retried payment succeeds, or failure is a decline → retries stop immediately.
- Retries exhausted and last attempt fails → customer sees the standard payment-failed page; order remains recoverable from the cart.
- Any retried payment completes (success or final failure) → retry outcome visible in the existing payments dashboard.

## Self-check

Every fact and criterion is present. Nothing has been added. The unspecified retry-policy flaw is preserved: no max attempts, backoff, retry window, idempotency guarantee (PSP idempotency keys), or cart/order-hold behavior during retries; no dependencies, links, deadlines, contacts, or sign-off are supplied.
