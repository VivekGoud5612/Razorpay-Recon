# Golden Reconciliation Scenarios

16 self-contained scenarios, SETL-G01 through SETL-G16 (distinct namespace — no collision with SETL-S01-S23 or any prior data).

| ID | Name | Expected Status | Primary Finding | Investigation Mode |
|---|---|---|---|---|
| SETL-G01 | clean_single_payment | RECONCILED | - | NOT_REQUIRED |
| SETL-G02 | clean_multi_payment | RECONCILED | - | NOT_REQUIRED |
| SETL-G03 | clean_with_refund | RECONCILED | - | NOT_REQUIRED |
| SETL-G04 | merchant_ledger_amount_difference | EXCEPTION | MERCHANT_LEDGER_AMOUNT_MISMATCH | GROUNDED |
| SETL-G05 | payment_amount_difference | EXCEPTION | PAYMENT_AMOUNT_MISMATCH | GROUNDED |
| SETL-G06 | duplicate_order | EXCEPTION | DUPLICATE_ORDER | GROUNDED |
| SETL-G07 | duplicate_payment | EXCEPTION | DUPLICATE_PAYMENT | GROUNDED |
| SETL-G08 | razorpay_order_not_found | EXCEPTION | RAZORPAY_ORDER_NOT_FOUND | ABSTAINED |
| SETL-G09 | bank_settlement_amount_difference | EXCEPTION | BANK_SETTLEMENT_AMOUNT_DIFFERENCE | GROUNDED |
| SETL-G10 | missing_bank_transaction | EXCEPTION | BANK_TRANSACTION_MISSING | GROUNDED |
| SETL-G11 | wrong_reference_mapping | EXCEPTION | WRONG_PAYMENT_REFERENCE | GROUNDED |
| SETL-G12 | pending_settlement | PENDING | - | NOT_REQUIRED |
| SETL-G13 | multi_source_disagreement | EXCEPTION | MULTI_SOURCE_DISAGREEMENT | ABSTAINED |
| SETL-G14 | timing_date_anomaly | EXCEPTION | SETTLEMENT_TIMING_ANOMALY | GROUNDED |
| SETL-G15 | grounded_unambiguous_reference_fix | EXCEPTION | WRONG_ORDER_REFERENCE | GROUNDED |
| SETL-G16 | abstain_genuine_ambiguity | EXCEPTION | AMBIGUOUS_MATCH | ABSTAINED |
