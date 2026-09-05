# SETL-G15 — grounded_unambiguous_reference_fix

**Business purpose:** Dedicated unambiguous case for testing confident AI resolution — amount, date, and UTR all uniquely identify the correct order despite a typo'd reference.

**Injected fault:** merchant_orders.csv row for MORD-01 has a one-character typo in razorpay_order_id; the correct order is uniquely identifiable by exact amount+date match with zero competing candidates.

**Expected status:** EXCEPTION
**Expected finding(s):** WRONG_ORDER_REFERENCE
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
MORD-01 references order_g15_01X, which does not exist, but order_g15_01 exists with an identical amount (₹33000.00) and identical date (2026-08-17), and no other order in this or any other scenario is a plausible alternative — a one-character reference typo, uniquely resolvable.

## Evidence notes
Claimed (nonexistent) order ID, the single real order matching on amount + date, absence of any competing candidate.
