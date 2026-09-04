"""
Generates 3 additional scenarios (21, 22, 23) in the exact same on-disk shape
as the converted 20-scenario dataset (razorpay.json / answers.json / README.md
/ merchant_faulty/*.csv), so the existing, unmodified scripts/seed_dataset.py
and scripts/run_dataset_scenarios.py pick them up generically -- no
scenario-specific code anywhere in either script.

Unlike scenarios 1-20, these are designed to genuinely reach the engine's
"reconciled" status: merchant_orders.csv references are all valid, and
(the one deliberate departure from scenarios 1-20's convention) ledger.csv
books the settlement NET (post MDR fee + GST), not the gross order value --
a legitimate real-world bookkeeping choice, and the only way
merchant_expected can equal razorpay_net under the existing, unchanged
reconciled-status formula (merchant_expected == razorpay_net == bank_observed).
Scenarios 1-20 book gross in their ledgers; that is their data and is not
touched here.

  scenario_21_clean_small           -- 5 orders, 1 payment each, no refunds
  scenario_22_clean_multi_payment   -- 10 orders, includes one processed refund
  scenario_23_clean_contextual_diff -- 8 orders; merchant-side narrative
                                        fields (customer_ref, invoice numbering,
                                        status wording, ledger account_code,
                                        POS terminal, description text) differ
                                        from what a naive mirror would produce,
                                        while every amount/reference that
                                        actually feeds reconciliation matches
                                        exactly.

All three are financially self-consistent: settlement_entries credit sums to
razorpay.json's settlement.amount, ledger.csv credit sums to the same net
figure, and every bank_statement.csv row's credit matches its settlement
entry's net exactly.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATASET_ROOT = Path("/home/vivek/Downloads/reconciliation_dataset_ours")

FEE_RATE = Decimal("0.0236")
TAX_RATE = Decimal("0.18")


def d2(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def paise(rupees: Decimal) -> int:
    return int((rupees * 100).to_integral_value())


def compute(gross: Decimal) -> dict:
    fee = d2(gross * FEE_RATE)
    tax = d2(fee * TAX_RATE)
    net = gross - fee - tax
    return {"gross": gross, "fee": fee, "tax": tax, "net": net}


def iso(dt: datetime) -> str:
    return dt.isoformat()


def epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def build_scenario(
    scenario_dir_name: str,
    scenario_num: str,
    merchant_name: str,
    settlement_id: str,
    orders_spec: list[dict],
    refunds_spec: list[dict],
    field_variant: bool,
) -> dict:
    """
    orders_spec: list of {gross: Decimal, created_at: datetime}
    refunds_spec: list of {order_index: int (0-based), amount: Decimal}
    field_variant: if True, use divergent (but reconciliation-irrelevant)
        merchant-side narrative fields.
    """
    scenario_dir = DATASET_ROOT / scenario_dir_name
    merchant_dir = scenario_dir / "merchant_faulty"
    merchant_dir.mkdir(parents=True, exist_ok=True)

    refunds_by_order = {r["order_index"]: r["amount"] for r in refunds_spec}

    orders_json = []
    payments_json = []
    settlement_entries_json = []
    refunds_json = []

    merchant_order_rows = []
    ledger_rows = []
    pos_rows = []
    gateway_rows = []
    bank_rows = []
    answers_findings = []

    total_amount = Decimal("0")
    total_fees = Decimal("0")
    total_tax = Decimal("0")

    captured_ats: list[datetime] = []

    for i, spec in enumerate(orders_spec, start=1):
        idx = i - 1
        gross = spec["gross"]
        created_at = spec["created_at"]
        captured_at = created_at
        captured_ats.append(captured_at)

        calc = compute(gross)
        fee, tax = calc["fee"], calc["tax"]
        refund_amount = refunds_by_order.get(idx, Decimal("0"))
        net = calc["net"] - refund_amount

        scenario_order_id = f"SC{scenario_num}-ORDER-{i:03d}"
        merchant_order_id = f"MORD-{scenario_num}-{i:03d}"
        payment_id = f"PAY-{scenario_num}-{i:03d}"
        entry_id = f"SETENTRY-{scenario_num}-{i:04d}"
        utr = f"UTR{scenario_num}{i:06d}"
        refund_id = f"RFND-{scenario_num}-{i:03d}" if refund_amount > 0 else None

        orders_json.append({
            "order_id": scenario_order_id,
            "amount": paise(gross),
            "currency": "INR",
            "status": "captured",
            "receipt": f"RCPT-SC{scenario_num}-{i:03d}",
            "created_at": epoch(created_at),
        })

        payments_json.append({
            "payment_id": payment_id,
            "order_id": scenario_order_id,
            "amount": paise(gross),
            "currency": "INR",
            "status": "captured",
            "method": "card",
            "fee": paise(fee),
            "tax": paise(tax),
            "created_at": epoch(created_at),
            "captured_at": epoch(captured_at),
        })

        if refund_amount > 0:
            refunds_json.append({
                "refund_id": refund_id,
                "payment_id": payment_id,
                "amount": paise(refund_amount),
                "currency": "INR",
                "status": "processed",
                "created_at": epoch(captured_at),
                "processed_at": epoch(captured_at),
            })

        settlement_entries_json.append({
            "entry_id": entry_id,
            "settlement_id": settlement_id,
            "entry_type": "payment",
            "amount": paise(gross),
            "debit": 0,
            "credit": paise(net),
            "fee": paise(fee),
            "tax": paise(tax),
            "payment_id": payment_id,
            "refund_id": refund_id,
            "transfer_id": None,
            "adjustment_id": None,
            "order_id": scenario_order_id,
            "settlement_utr": utr,
            "description": "Payment settlement",
            "created_at": 0,  # derived by seed_dataset.py from the payment's captured_at
            "settled_at": 0,
        })

        total_amount += net
        total_fees += fee
        total_tax += tax

        # --- merchant-side CSV rows ---
        if field_variant:
            customer_ref = f"CUST-{scenario_num}-{1000 + i}"
            invoice_id = f"FY26-INV-{i:05d}"
            order_status = "completed"
            account_code = "REVENUE_NET_SETTLED"
            ledger_reference = f"payout_{scenario_num}_{i:04d}"
            ledger_description = "Net settlement booked to revenue (post-MDR)"
            terminal_id = f"STORE-{(i % 3) + 1}-POS"
            gateway_status = "settled"
        else:
            customer_ref = f"CUST-{scenario_num}-{i:03d}"
            invoice_id = f"INV-{scenario_num}-{i:03d}"
            order_status = "paid"
            account_code = "SALES_REVENUE"
            ledger_reference = utr
            ledger_description = "Merchant ledger entry (CLEAN_MATCH)"
            terminal_id = f"TERM-{scenario_num}"
            gateway_status = "success"

        merchant_order_rows.append({
            "merchant_order_id": merchant_order_id,
            "razorpay_order_id": scenario_order_id,
            "amount": f"{gross:.2f}",
            "currency": "INR",
            "customer_ref": customer_ref,
            "invoice_id": invoice_id,
            "status": order_status,
            "created_at": iso(created_at),
        })

        ledger_rows.append({
            "ledger_entry_id": f"LED-{scenario_num}-{i:04d}",
            "merchant_order_id": merchant_order_id,
            "account_code": account_code,
            "entry_type": "credit",
            "debit": "0.00",
            "credit": f"{net:.2f}",
            "currency": "INR",
            "posted_at": iso(created_at),
            "reference": ledger_reference,
            "description": ledger_description,
        })

        pos_rows.append({
            "pos_transaction_id": f"POS-{scenario_num}-{i:04d}",
            "merchant_order_id": merchant_order_id,
            "amount": f"{gross:.2f}",
            "currency": "INR",
            "transaction_date": iso(created_at),
            "status": gateway_status,
            "terminal_id": terminal_id,
        })

        gateway_rows.append({
            "gateway_transaction_id": f"GTW-{scenario_num}-{i:04d}",
            "merchant_order_id": merchant_order_id,
            "gateway_order_id": scenario_order_id,
            "amount": f"{gross:.2f}",
            "currency": "INR",
            "status": gateway_status,
            "created_at": iso(created_at),
        })

        bank_rows.append({
            "transaction_id": f"BTX-{scenario_num}-{i:04d}",
            "utr": utr,
            "transaction_date": iso(created_at),
            "value_date": iso(created_at),
            "description": f"Settlement credit - {merchant_name}",
            "debit": "0.00",
            "credit": f"{net:.2f}",
            "balance": "0.00",
            "reference": utr,
        })

        answers_findings.append({
            "merchant_order_id": merchant_order_id,
            "razorpay_order_id": scenario_order_id,
            "razorpay_payment_id": payment_id,
            "expected_exception_code": "CLEAN_MATCH",
            "expected_settlement_net": f"{net:.2f}",
            "should_abstain": False,
        })

    utr_settle = f"SETTLE-UTR-{scenario_num}-001"
    settlement_json = {
        "settlement_id": settlement_id,
        "amount": paise(total_amount),
        "fees": paise(total_fees),
        "tax": paise(total_tax),
        "currency": "INR",
        "utr": utr_settle,
        "status": "processed",
    }

    razorpay_json = {
        "merchant_name": merchant_name,
        "settlement": settlement_json,
        "orders": orders_json,
        "payments": payments_json,
        "settlement_entries": settlement_entries_json,
        "refunds": refunds_json,
        "transfers": [],
        "adjustments": [],
    }

    (scenario_dir / "razorpay.json").write_text(json.dumps(razorpay_json, indent=2))

    answers_json = {
        "scenario_id": f"scenario_{scenario_num}",
        "merchant": merchant_name,
        "settlement_id": settlement_id,
        "expected_findings": answers_findings,
    }
    (scenario_dir / "answers.json").write_text(json.dumps(answers_json, indent=2))

    def write_csv(name: str, rows: list[dict]) -> None:
        with (merchant_dir / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv("merchant_orders.csv", merchant_order_rows)
    write_csv("ledger.csv", ledger_rows)
    write_csv("pos.csv", pos_rows)
    write_csv("other_gateway.csv", gateway_rows)
    write_csv("bank_statement.csv", bank_rows)

    readme = f"""# Scenario {scenario_num} — {merchant_name}

## Scenario

Newly authored clean/PASS scenario (not part of the original converted 20)
built to genuinely reach the engine's `reconciled` status: every
merchant_order->Razorpay reference is valid, every payment/refund is real,
and merchant ledger books the settlement NET (post-MDR-fee, post-GST, and
post-refund where applicable) so merchant_expected == razorpay_net ==
bank_observed exactly.

Records: {len(orders_spec)}
Expected breakdown: CLEAN_MATCH={len(orders_spec)}

## Directory

- `merchant_faulty/merchant_orders.csv` (misnomer kept for directory-shape
  consistency with scenarios 1-20 -- there is no injected fault here)
- `merchant_faulty/ledger.csv`
- `merchant_faulty/pos.csv`
- `merchant_faulty/other_gateway.csv`
- `merchant_faulty/bank_statement.csv`
- `razorpay.json`
- `answers.json`

## Settlement

Settlement ID: `{settlement_id}`

## Expected exception types

CLEAN_MATCH={len(orders_spec)} (expected overall status: **reconciled**)

## Evaluation

`answers.json` is frozen ground truth for evaluation only. The application
must determine the result from persisted Razorpay and merchant data; it
must not read the answer file.
"""
    (scenario_dir / "README.md").write_text(readme)

    return {
        "scenario": scenario_dir_name,
        "settlement_id": settlement_id,
        "orders": len(orders_spec),
        "total_net": str(total_amount),
    }


def main() -> None:
    base_dt = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

    # --- Scenario 21: small clean settlement, 5 orders, 1 payment each ---
    orders_21 = [
        {"gross": Decimal(g), "created_at": base_dt.replace(day=1 + i)}
        for i, g in enumerate(["5000.00", "7500.00", "3200.00", "12000.00", "890.00"])
    ]
    r21 = build_scenario(
        "scenario_21_clean_small", "21", "Willow Creek Stationery", "SETL-21-001",
        orders_21, refunds_spec=[], field_variant=False,
    )

    # --- Scenario 22: multi-payment clean settlement with one processed refund ---
    gross_values_22 = ["4200.00", "15800.00", "2300.00", "9900.00", "6100.00",
                        "21000.00", "1750.00", "8300.00", "13400.00", "5600.00"]
    orders_22 = [
        {"gross": Decimal(g), "created_at": base_dt.replace(day=1 + (i % 28))}
        for i, g in enumerate(gross_values_22)
    ]
    # order index 3 (0-based) gets a partial refund
    r22 = build_scenario(
        "scenario_22_clean_multi_payment", "22", "Fernbank Wholesale Traders", "SETL-22-001",
        orders_22, refunds_spec=[{"order_index": 3, "amount": Decimal("1500.00")}],
        field_variant=False,
    )

    # --- Scenario 23: clean, but merchant-side narrative fields differ ---
    gross_values_23 = ["6700.00", "11200.00", "3050.00", "18900.00",
                        "990.00", "24500.00", "7300.00", "2100.00"]
    orders_23 = [
        {"gross": Decimal(g), "created_at": base_dt.replace(day=1 + (i % 28))}
        for i, g in enumerate(gross_values_23)
    ]
    r23 = build_scenario(
        "scenario_23_clean_contextual_diff", "23", "Marlow & Finch Trading Co.", "SETL-23-001",
        orders_23, refunds_spec=[], field_variant=True,
    )

    for r in (r21, r22, r23):
        print(json.dumps(r))


if __name__ == "__main__":
    main()
