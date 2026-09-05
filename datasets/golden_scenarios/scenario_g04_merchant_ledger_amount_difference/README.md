# SETL-G04 — merchant_ledger_amount_difference

**Business purpose:** Merchant's own ledger records a different gross amount than Razorpay's order/payment — a bookkeeping drift, not a Razorpay-side problem.

**Injected fault:** ledger.csv row for MORD-02 understates the true payment amount by ₹500.00.

**Expected status:** EXCEPTION
**Expected finding(s):** MERCHANT_LEDGER_AMOUNT_MISMATCH
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
Merchant's internal ledger amount for this order differs from the Razorpay-confirmed payment amount by exactly ₹500.00; no other order in this dataset is affected, and Razorpay-side data is internally consistent.

## Evidence notes
razorpay payment amount (order_g04_02), merchant ledger row for MORD-02, delta computation.
