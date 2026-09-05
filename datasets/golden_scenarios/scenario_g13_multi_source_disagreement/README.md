# SETL-G13 — multi_source_disagreement

**Business purpose:** Ledger, POS, and other-gateway records for the same order all report different amounts — genuine multi-source conflict.

**Injected fault:** ledger.csv, pos.csv, and other_gateway.csv all report different amounts (24000 / 23500 / 24600) for the same order — a real three-way conflict, not a two-way mismatch.

**Expected status:** EXCEPTION
**Expected finding(s):** MULTI_SOURCE_DISAGREEMENT
**Investigation required:** True
**Investigation mode:** ABSTAINED



## Root cause (if grounded)
N/A — abstained or not required.

## Evidence notes
Three independent sources (ledger, POS, other-gateway) report three different amounts for the same order, with no fourth source or metadata to determine which is authoritative beyond Razorpay's own record — genuinely conflicting evidence.
