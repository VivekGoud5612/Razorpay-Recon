# Rich Reconciliation Dataset — 60 Records

## Dataset

One settlement contains 60 realistic-looking transactions across multiple merchant categories.

Razorpay is the clean/reference side.

Files:
- `razorpay.json`
- `answers.json`
- `merchant/merchant_orders.csv`
- `merchant/ledger.csv`
- `merchant/pos.csv`
- `merchant/other_gateway.csv`
- `merchant/bank_statement.csv`

## Financial model

For every payment:

`gross amount - fee - tax = net settlement amount`

Settlement:
- Gross: 827670.00 INR
- Fees: 19533.02 INR
- Tax: 3515.92 INR
- Net: 804621.06 INR

There is one settlement:
`SETL-RICH-001`

Each settlement entry has its own UTR:
`RICH-UTR-0001 ... RICH-UTR-0060`

Each clean bank credit corresponds to its payment's net amount.

## Controlled merchant-side anomalies

1. Merchant order amount mismatch — record 8
2. Ledger over — record 11
3. POS amount mismatch — record 20
4. Gateway amount mismatch — record 30
5. Bank short settlement — record 40

The rest of the records are intended to be internally consistent.

## Design intent

The dataset is deliberately larger and less repetitive than the earlier scenario fixtures:
- 60 orders
- varied amounts
- varied payment methods
- multiple merchant names
- realistic order/payment/settlement relationships
- deterministic UTR mapping
- explicit fee/tax/net calculations
- controlled faults for deterministic reconciliation and AI investigation

Refunds, transfers, and adjustments are currently empty so they can be added selectively to later test packs without contaminating the baseline.
