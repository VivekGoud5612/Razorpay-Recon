# SETL-G07 — duplicate_payment

**Business purpose:** Merchant ledger references the same razorpay_payment_id twice — distinct from a duplicate order.

**Injected fault:** ledger.csv contains two rows referencing the same razorpay_payment_id.

**Expected status:** EXCEPTION
**Expected finding(s):** DUPLICATE_PAYMENT
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
ledger.csv references razorpay_payment_id pay_g07_01 twice under two order_refs — a single real payment double-booked in the merchant's ledger.

## Evidence notes
Both ledger.csv rows, the single matching Razorpay payment.
