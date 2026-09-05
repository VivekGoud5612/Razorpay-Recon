# SETL-G14 — timing_date_anomaly

**Business purpose:** Bank credit arrives dated far outside the expected T+2 settlement window from capture.

**Injected fault:** bank_statement.csv credit date is 19 days after capture, versus the expected ~T+2 working days.

**Expected status:** EXCEPTION
**Expected finding(s):** SETTLEMENT_TIMING_ANOMALY
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
The bank credit for this settlement landed 19 days after the payment's capture date, far outside the standard T+2 working-day settlement window, while amounts fully reconcile — timing anomaly, not an amount discrepancy.

## Evidence notes
Payment capture date, bank statement credit date, computed elapsed days versus the documented T+2 norm.
