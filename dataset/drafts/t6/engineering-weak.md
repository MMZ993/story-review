# engineering-weak — T6 draft

## retry

A temporary PSP outage, timeout or 5xx, fails the order outright today: the customer sees an error, abandons the cart, and support tickets follow. The order service already distinguishes a PSP decline from a PSP error, so a legitimate retry is identifiable. Payment errors were 38% of abandoned carts last quarter and the payments team estimates roughly a fifth are transient PSP failures. Support gets ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month. This is automatic retry for PSP errors only, not retries for declines, changes to decline messaging, or native apps.

If payment failed due to a PSP error, not a decline, retry automatically without customer action. Stop retries immediately when a retried payment succeeds or the failure is a decline. If retries are exhausted and the last attempt fails, show the standard payment-failed page and leave the order recoverable from the cart. Whenever a retried payment completes, whether success or final failure, make the retry outcome visible in the existing payments dashboard.

## Self-check

Every canonical fact and criterion is present in prose. Nothing was added. The missing retry policy specifics, idempotency guarantee, and cart/order-hold behavior during retries are preserved.
