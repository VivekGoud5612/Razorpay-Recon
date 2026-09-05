# SETL-G12 — pending_settlement

**Business purpose:** Settlement has not yet been processed/credited — a timing state, not an error.

**Injected fault:** None — this is a genuine PENDING state (T+2 not yet elapsed), the engine must NOT flag this as BANK_TRANSACTION_MISSING.

**Expected status:** PENDING
**Expected finding(s):** None
**Investigation required:** False
**Investigation mode:** NOT_REQUIRED

**ENGINE_CAPABILITY_REQUIRED:** Engine must distinguish settlement_status='pending' from a genuinely missing bank transaction on a processed settlement (see G10). If the current engine cannot read/respect settlement status, mark this ENGINE_CAPABILITY_REQUIRED and do not force a fix tonight.

## Root cause (if grounded)
N/A — abstained or not required.

## Evidence notes
Settlement status explicitly 'pending' on the Razorpay side — no bank credit is expected yet, this is not a discrepancy.
