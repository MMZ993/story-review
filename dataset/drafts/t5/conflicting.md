# conflicting — T5 draft

Title: Last-used payment pre-selection

Description:
As the checkout service, we need to pre-select and charge the returning customer's last used payment method, so that the one-page checkout redesign can remove the payment selection step.

Checkout currently shows all available payment methods with no default; returning customers re-pick their method on every order. The one-page checkout redesign under this feature aims to remove checkout steps. Funnel analytics show returning customers spend a median 11 seconds selecting a payment method they used on the previous order. UX research flagged method selection as the top friction point for returning customers; marketing asked for a "one-tap pay" experience.

Scope is web checkout for signed-in returning customers. Out of scope are guest checkout, native apps, and adding new payment methods.

Acceptance Criteria field:
- Returning customer with a previously used method, checkout loads → last used method pre-selected.
- Pre-selected method, customer confirms the order → payment charged with that method without a separate selection step.
- Last used method no longer available, checkout loads → no method pre-selected; message explains why.

## Self-check

Every fact and criterion is present. Nothing has been added. The unmitigated charge-without-selection-step versus step-removal conflict is preserved: no explicit confirmation action, visible Pay button, method-change mechanism, or "pre-selected method and total shown" criterion; no dependencies, links, deadlines, contacts, or sign-off are supplied.
