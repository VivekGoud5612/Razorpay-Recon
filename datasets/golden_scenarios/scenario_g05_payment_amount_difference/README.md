# SETL-G05 — payment_amount_difference

**Business purpose:** Merchant's order-level record (not ledger) disagrees with the actual Razorpay payment amount — a different source than G04.

**Injected fault:** merchant_orders.csv row for MORD-01 overstates amount by ₹1200.00; ledger.csv for the same order is correct, isolating which source is wrong.

**Expected status:** EXCEPTION
**Expected finding(s):** PAYMENT_AMOUNT_MISMATCH
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
Merchant's order-level record overstates the payment amount by ₹1200.00 versus the Razorpay-confirmed payment; ledger.csv for the same order agrees with Razorpay, isolating the discrepancy to merchant_orders.csv specifically.

## Evidence notes
razorpay payment record, merchant_orders.csv row, ledger.csv row (which agrees with Razorpay) as a cross-check.
