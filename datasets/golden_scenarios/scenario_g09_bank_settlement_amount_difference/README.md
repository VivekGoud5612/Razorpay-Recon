# SETL-G09 — bank_settlement_amount_difference

**Business purpose:** Bank-credited amount differs from Razorpay's computed net settlement — a fee/tax drift, not a reference problem.

**Injected fault:** bank_statement.csv credited amount reflects a stale 1.8% MDR assumption instead of the actual 2.0% rate.

**Expected status:** EXCEPTION
**Expected finding(s):** BANK_SETTLEMENT_AMOUNT_DIFFERENCE
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
Bank-credited amount exceeds Razorpay's computed net settlement by an amount consistent with the bank/merchant applying a lower MDR rate (1.8%) than Razorpay's actual rate (2.0%) — a fee-assumption drift, fully explained by the delta.

## Evidence notes
Razorpay settlement computation breakdown (gross, MDR, GST), bank statement credited amount, delta re-derivation under the stale MDR assumption.
