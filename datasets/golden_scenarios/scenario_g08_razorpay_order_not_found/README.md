# SETL-G08 — razorpay_order_not_found

**Business purpose:** Merchant references an order ID that genuinely does not exist anywhere in Razorpay's records.

**Injected fault:** merchant_orders.csv/ledger.csv row for MORD-03 references order/payment IDs that were never generated on the Razorpay side at all (not a typo of a real ID — genuinely absent).

**Expected status:** EXCEPTION
**Expected finding(s):** RAZORPAY_ORDER_NOT_FOUND
**Investigation required:** True
**Investigation mode:** ABSTAINED



## Root cause (if grounded)
N/A — abstained or not required.

## Evidence notes
Merchant claims an order/payment ID that has no counterpart anywhere in Razorpay's data — genuinely insufficient evidence to determine what the merchant actually meant.
