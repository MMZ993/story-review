# engineering-weak — T2 draft (from T1 id 14)

## Must-retain facts

- A temporary PSP outage (timeout or 5xx) fails the order outright today; the customer sees an error, the cart is abandoned, and support tickets follow.
- The order service already distinguishes PSP decline from PSP error, so a legitimate retry is identifiable.
- Payment errors were 38% of abandoned carts last quarter.
- The payments team estimates roughly a fifth are transient PSP failures.
- Support receives ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month.
- Scope is automatic retry for PSP errors only.
- Out of scope: retries for declines, changes to the decline messaging, and native apps.
- When a payment fails because of a PSP error, not a decline, the system retries payment automatically without customer action.
- When a retried payment succeeds or a failure is a decline, retries stop immediately.
- When retries are exhausted and the last attempt fails, the customer sees the standard payment-failed page and the order remains recoverable from the cart.
- When any retried payment completes, whether success or final failure, the retry outcome is visible in the existing payments dashboard.

## Must-not-add

- Do not specify a maximum retry count, backoff, or retry window.
- Do not add PSP idempotency keys or another idempotency guarantee for retried charges.
- Do not define cart or order hold behavior while retries run.
- Do not add facts, dependencies, links, deadlines, contacts, or sign-off not present in T1.

## T2 rendering

**Title:** Automatic payment retry on PSP failure

**Description:** A temporary PSP outage (timeout or 5xx) fails the order outright today: the customer sees an error, the cart is abandoned, and support tickets follow. The order service already distinguishes PSP decline from PSP error, so a legitimate retry is identifiable.

**Reason:** Payment errors were 38% of abandoned carts last quarter, and the payments team estimates roughly a fifth are transient PSP failures. Support receives ~120 payment-failure tickets/month; halving that saves about 2 agent-days per month.

**Implementation:** Implement automatic retry for PSP errors only. Retries for declines, changes to the decline messaging, and native apps are out of scope.

**For this story:**

1. Verify that a payment failing due to a PSP error, rather than a decline, is retried automatically without customer action.
2. Verify that retries stop immediately when a retried payment succeeds or when a failure is a decline.
3. Verify that, when retries are exhausted and the last attempt fails, the customer sees the standard payment-failed page and the order remains recoverable from the cart.
4. Verify that the retry outcome is visible in the existing payments dashboard whenever a retried payment completes, whether by success or final failure.

---

**Acceptance Criteria field:** empty.

## Self-check

- Every must-retain fact is present.
- Nothing beyond the T1 facts was added.
- Retry policy, idempotency, and cart/order-hold gaps remain undefined.
- The Acceptance Criteria field is empty.
