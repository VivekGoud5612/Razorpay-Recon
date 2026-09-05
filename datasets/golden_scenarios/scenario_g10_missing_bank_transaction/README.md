# SETL-G10 — missing_bank_transaction

**Business purpose:** Settlement and orders are fully valid Razorpay-side, but the bank statement has zero rows for it — genuinely missing, not a wrong reference.

**Injected fault:** bank_statement.csv contains zero rows for this settlement (file present but empty of relevant entries) — a genuinely missing bank transaction, self-contained within this scenario's own data.

**Expected status:** EXCEPTION
**Expected finding(s):** BANK_TRANSACTION_MISSING
**Investigation required:** True
**Investigation mode:** GROUNDED



## Root cause (if grounded)
Razorpay-side settlement and both underlying orders/payments are fully consistent and captured, but no corresponding bank statement entry exists for this settlement's UTR — the credit has not landed, or the statement is incomplete.

## Evidence notes
Razorpay settlement + order/payment records (internally consistent), absence of any bank_statement.csv row for this settlement's UTR.
