# SETL-G06 — duplicate_order

**Business purpose:** Merchant accidentally uploads the same order twice in merchant_orders.csv.

**Injected fault:** merchant_orders.csv contains two rows (MORD-02, MORD-02-DUP) both referencing the same razorpay_order_id.

**Expected status:** EXCEPTION
**Expected finding(s):** DUPLICATE_ORDER
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
The same razorpay_order_id appears twice in merchant_orders.csv under two different order_refs (MORD-02 and MORD-02-DUP), both pointing to the same real Razorpay order — a genuine upload duplication, not two separate orders.

## Evidence notes
Both merchant_orders.csv rows, the single matching Razorpay order.
