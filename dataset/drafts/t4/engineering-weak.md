# engineering-weak — T4 draft

## T4 rendering

**Title:** As a customer, I want automatic payment retry on PSP failure so that a temporary PSP outage does not fail my order outright.

**Description:**

Today, a temporary PSP outage, including a timeout or 5xx, fails the order outright: the customer sees an error, abandons the cart, and support tickets follow. The order service already distinguishes a PSP decline from a PSP error, so a legitimate retry is identifiable.

Payment errors were 38% of abandoned carts last quarter, and the payments team estimates roughly a fifth are transient PSP failures. Support receives ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month. Scope is automatic retry for PSP errors only; retries for declines, changes to the decline messaging, and native apps are out of scope.

**Acceptance Criteria field:**

- When payment fails due to a PSP error rather than a decline, the system retries automatically without customer action.
- If a retried payment succeeds, or the failure is a decline, retries stop immediately.
- If retries are exhausted and the last attempt fails, the customer sees the standard payment-failed page and the order remains recoverable from the cart.
- When any retried payment completes, whether successfully or with final failure, the retry outcome is visible in the existing payments dashboard.

## Self-check

- Every canonical fact and criterion is present; nothing beyond them is added.
- No maximum attempts, backoff, retry window, idempotency guarantee, or cart/order-hold behavior during retries is specified.
- The title's customer, automatic retry on PSP failure, and temporary-outage benefit also appear in the body.
