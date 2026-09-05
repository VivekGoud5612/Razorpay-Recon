# SETL-G11 — wrong_reference_mapping

**Business purpose:** Merchant ledger references a real, existing Razorpay payment — but the WRONG one, swapped with another real order's payment.

**Injected fault:** ledger.csv row for MORD-01 cites the payment ID belonging to MORD-02 instead of its own — amounts are identical (making amount alone insufficient), but dates uniquely resolve the correct mapping.

**Expected status:** EXCEPTION
**Expected finding(s):** WRONG_PAYMENT_REFERENCE
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
MORD-01's ledger row cites pay_g11_02, but MORD-01's own merchant_orders.csv date (2026-08-15) matches pay_g11_01's date exactly, while pay_g11_02 is dated 2026-08-20 — the date evidence uniquely resolves which payment MORD-01 actually corresponds to.

## Evidence notes
merchant_orders.csv date for MORD-01, both real payments' dates, uniquely resolving via date match despite identical amounts.
