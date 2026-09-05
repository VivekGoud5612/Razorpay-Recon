# SETL-G16 — abstain_genuine_ambiguity

**Business purpose:** Dedicated ambiguous case for testing correct abstention — two real orders share identical amount AND identical date, so a reference fault cannot be uniquely resolved.

**Injected fault:** MORD-01's razorpay_order_id is broken/unknown, and TWO real orders are equally plausible matches (same amount, same date) — deliberately irreducible ambiguity, not just missing data.

**Expected status:** EXCEPTION
**Expected finding(s):** AMBIGUOUS_MATCH
**Investigation required:** True
**Investigation mode:** ABSTAINED



## Root cause (if grounded)
N/A — abstained or not required.

## Evidence notes
Two real orders (order_g16_01, order_g16_02) share an identical amount (₹18000.00) and identical date (2026-08-18) — no evidence in this dataset distinguishes which one MORD-01 actually refers to. Correct behavior is abstention, not a guess.
