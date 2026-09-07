# conflicting — T6 draft

## last one

Checkout currently shows every available payment method with no default, so returning customers pick their method again on every order. The one-page checkout redesign under this feature is meant to remove checkout steps. Funnel analytics say returning customers spend a median 11 seconds selecting the method used on their previous order. UX research called method selection the top friction point for returning customers, and marketing asked for a "one-tap pay" experience. This is web checkout for signed-in returning customers, not guest checkout, native apps, or new payment methods.

When a returning customer has a previously used method and checkout loads, pre-select the last used method. With that pre-selected method, when the customer confirms the order, charge payment with that method without a separate selection step. If the last used method is no longer available when checkout loads, pre-select nothing and explain why in a message.

## Self-check

Every canonical fact and criterion is present in prose. Nothing was added. The conflict remains unmitigated: no explicit confirmation action, visible Pay button, method-change mechanism, or pre-selected-method-and-total-shown criterion.
