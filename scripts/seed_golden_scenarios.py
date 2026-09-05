"""
Seeds the 16 golden scenarios (datasets/golden_scenarios) into this project,
through the same real, production application paths used for the other
datasets -- no fake/shortcut order-creation path, no direct row insertion for
anything the app itself is supposed to produce.

Why this script exists (baseline finding, not fixed here): the golden
dataset's razorpay.json/merchant_faulty/*.csv use a deliberately minimal
schema (`order_ref`, `date`, `credited_amount`, no `settlement_entries`, no
`currency`, no fee model) that does not match the application's real
ingestion contract or SettlementReconciliationData shape. This mirrors
exactly the same gap the OLD 20-scenario dataset had against its own
`scn_XXX` source form before `merchant_seeded/` existed. This script is that
same kind of derivation step -- it never edits a golden scenario's source
files; it writes a new `merchant_seeded/` directory next to `merchant_faulty/`
and seeds Postgres, deriving everything from the untouched originals.

Phase 1 -- real Razorpay orders:
    Every order in a scenario's razorpay.json is created through the
    existing CreateRazorpayOrderUseCase -> RazorpayApiGateway (live
    Razorpay test-mode API) -> RazorpayPostgresRepository, exactly as
    scripts/seed_dataset.py does for the other dataset. Idempotent: looked
    up by `receipt` first (receipt = the scenario's own order id, e.g.
    "order_g01_01" -- a deterministic, stable reference; orders are never
    mapped by row position). A scenario order id genuinely absent from
    razorpay.json's `orders` list (G08/G15/G16's intentionally-wrong/missing
    references) is never created, so a merchant CSV reference to it keeps
    resolving to nothing.

Phase 2 -- Razorpay-side settlement state:
    payments/refunds are written via RazorpayPostgresRepository from
    razorpay.json verbatim (amount, status, order/payment linkage). The one
    thing razorpay.json does NOT supply at all: settlement_entries and a
    settlement UTR/amount/fees. Both are derived, not invented arbitrarily:
      - Every scenario's bank_statement.csv (when non-empty) already states
        an explicit `credited_amount` that equals, to the cent,
        sum(payment.amount - round(payment.amount * FEE_RATE, 2)) -
        sum(refund.amount) -- i.e. this dataset's fee model is a flat
        FEE_RATE with NO separate GST/tax layer (unlike the older 20-scenario
        dataset, which has both). Verified against every scenario whose
        answers.json states a razorpay_net figure before writing this.
      - One settlement_entry is synthesized per payment (entry_type=
        "payment", credit=amount-fee) and per refund (entry_type="refund",
        debit=amount) using that fee model -- there is no other value they
        could legitimately take that would reproduce the dataset's own
        stated net.
      - settlement.utr and every entry's settlement_utr are set to the
        SAME value: the scenario's own bank_statement.csv `utr` column when
        a bank row exists, else the same "UTR-{SCENARIO_ID}-001" convention
        every scenario that DOES have a bank row already uses (verified
        below) -- never an arbitrary/random token.

Phase 3 -- merchant_seeded/ (ingestible CSVs):
    merchant_faulty/*.csv columns are renamed/enriched to the columns the
    real ingestion normalizer/validator actually requires (e.g. `order_ref`
    -> already an accepted alias for merchant_order_id; `currency` added,
    since every scenario is uniformly INR and the source omits it; ledger's
    `razorpay_payment_id` preserved verbatim as the ledger entry's
    `reference` column, since G07/G11's entire fault is expressed through
    that value). Amounts/dates/references are copied verbatim from the
    golden source -- nothing about which rows exist or what they claim is
    changed. A source file with zero data rows (e.g. G10/G12's empty
    bank_statement.csv) is not written into merchant_seeded/ at all and is
    never submitted to the batch endpoint -- the normalizer treats an empty
    file as entity_type="unknown" and rejects it outright, and a real
    merchant integration would simply not upload a file it has no rows for.

Output per scenario, under <scenario_dir>/:
    order_mapping.json  -- scenario order_id -> real order_id (+ reused flag)
    merchant_seeded/     -- ingestible CSVs, only for sources with >=1 row

A top-level golden_seed_report.json is written under datasets/golden_scenarios/.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import razorpay
from dotenv import load_dotenv

from recon.application.razorpay.dto.requests import CreateOrderRequest
from recon.application.razorpay.use_cases.create_orders import CreateRazorpayOrderUseCase
from recon.domain.razorpay.payment import RazorpayPayment
from recon.domain.razorpay.refund import RazorpayRefund
from recon.domain.razorpay.settlement import RazorpaySettlement
from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry
from recon.infrastructure.persistence.postgres.config import DatabaseConfig
from recon.infrastructure.persistence.postgres.connection import PostgresConnection
from recon.infrastructure.persistence.postgres.repositories.razorpay_repository import (
    RazorpayPostgresRepository,
)
from recon.infrastructure.razorpay.gateway import RazorpayApiGateway

load_dotenv()

DATASET_ROOT = Path(__file__).resolve().parent.parent / "datasets" / "golden_scenarios"
FEE_RATE = Decimal("0.0236")
CONCURRENCY = 3
MAX_RETRIES = 8
RETRY_BASE_DELAY = 1.5


def d2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def paise_from_rupees(value) -> int:
    return int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def to_datetime(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)


async def existing_order_id(db: PostgresConnection, receipt: str) -> str | None:
    async with db.acquire() as conn:
        return await conn.fetchval(
            "SELECT order_id FROM razorpay_orders WHERE receipt = $1", receipt
        )


async def create_order_with_retry(use_case: CreateRazorpayOrderUseCase, order: dict) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            return await use_case.execute(
                CreateOrderRequest(
                    amount=paise_from_rupees(order["amount"]),
                    currency="INR",
                    receipt=order["id"],
                )
            )
        except razorpay.errors.BadRequestError as exc:
            if "too many requests" not in str(exc).lower() or attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_BASE_DELAY * (2**attempt)
            print(f"  rate-limited on receipt={order['id']!r}, retrying in {delay:.1f}s", flush=True)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def seed_orders(
    orders: list[dict],
    use_case: CreateRazorpayOrderUseCase,
    db: PostgresConnection,
) -> tuple[dict[str, str], list[dict]]:
    mapping: dict[str, str] = {}
    report: list[dict] = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(order: dict) -> None:
        async with sem:
            receipt = order["id"]
            found = await existing_order_id(db, receipt)
            if found:
                mapping[order["id"]] = found
                report.append({"scenario_order_id": order["id"], "receipt": receipt, "real_order_id": found, "reused": True})
                return

            real_id = await create_order_with_retry(use_case, order)
            mapping[order["id"]] = real_id
            report.append({"scenario_order_id": order["id"], "receipt": receipt, "real_order_id": real_id, "reused": False})

    await asyncio.gather(*(one(o) for o in orders))
    return mapping, report


async def correct_order_timestamps(orders: list[dict], mapping: dict[str, str], db: PostgresConnection) -> None:
    """Same rationale as seed_dataset.py's version: the live API assigns
    created_at = wall-clock call time; this restores the scenario's intended
    historical date so temporal checks don't spuriously fire."""
    async with db.acquire() as conn:
        await conn.executemany(
            "UPDATE razorpay_orders SET created_at = $1 WHERE order_id = $2",
            [(to_datetime(o["date"]), mapping[o["id"]]) for o in orders if o["id"] in mapping],
        )


def resolve_utr(scenario_id: str, bank_rows: list[dict]) -> str:
    if bank_rows:
        return bank_rows[0]["utr"]
    # Every scenario that DOES have a bank row uses "UTR-{G0N}-001" (e.g.
    # "UTR-G09-001", not "UTR-SETL-G09-001") -- match that convention rather
    # than the raw "SETL-G10"-shaped scenario_id.
    suffix = scenario_id.removeprefix("SETL-")
    return f"UTR-{suffix}-001"


async def seed_settlement_state(
    scenario_id: str,
    rzp: dict,
    bank_rows: list[dict],
    order_mapping: dict[str, str],
    repo: RazorpayPostgresRepository,
) -> dict:
    settlement_json = rzp["settlement"]
    payments = settlement_json.get("payments", [])
    refunds = settlement_json.get("refunds", [])
    utr = resolve_utr(scenario_id, bank_rows)

    payment_captured_at: dict[str, datetime] = {}
    created_payment_ids: set[str] = set()
    skipped: list[dict] = []
    entries: list[RazorpaySettlementEntry] = []
    total_amount = Decimal("0")
    total_fees = Decimal("0")

    for i, p in enumerate(payments, start=1):
        real_order_id = order_mapping.get(p["order_id"])
        if real_order_id is None:
            skipped.append({"kind": "payment", "id": p["id"], "reason": f"order {p['order_id']} was never created (intentionally missing)"})
            continue

        captured_at = to_datetime(p["date"])
        amount = d2(p["amount"])
        fee = d2(amount * FEE_RATE)

        payment = RazorpayPayment(
            payment_id=p["id"],
            order_id=real_order_id,
            amount=amount,
            currency="INR",
            status=p["status"],
            method="card",
            fee=fee,
            tax=Decimal("0"),
            created_at=captured_at,
            captured_at=captured_at if p["status"] == "captured" else None,
        )
        await repo.save_payment(payment)
        created_payment_ids.add(p["id"])
        payment_captured_at[p["id"]] = captured_at

        entries.append(
            RazorpaySettlementEntry(
                entry_id=f"SETENTRY-{scenario_id}-{i:04d}",
                settlement_id=settlement_json["id"],
                entry_type="payment",
                amount=amount,
                debit=Decimal("0"),
                credit=amount - fee,
                fee=fee,
                tax=Decimal("0"),
                payment_id=p["id"],
                refund_id=None,
                transfer_id=None,
                adjustment_id=None,
                order_id=real_order_id,
                settlement_utr=utr,
                description="Payment settlement",
                created_at=captured_at,
                settled_at=None,  # filled in once processed_at is known
            )
        )
        total_amount += amount
        total_fees += fee

    created_refund_ids: set[str] = set()
    for j, r in enumerate(refunds, start=1):
        if r["payment_id"] not in created_payment_ids:
            skipped.append({"kind": "refund", "id": r["id"], "reason": f"payment {r['payment_id']} was skipped/not created"})
            continue

        anchor = payment_captured_at[r["payment_id"]]
        amount = d2(r["amount"])
        refund = RazorpayRefund(
            refund_id=r["id"],
            payment_id=r["payment_id"],
            amount=amount,
            currency="INR",
            status="processed",
            created_at=anchor,
            processed_at=anchor,
        )
        await repo.save_refund(refund)
        created_refund_ids.add(r["id"])

        entries.append(
            RazorpaySettlementEntry(
                entry_id=f"SETENTRY-{scenario_id}-R{j:04d}",
                settlement_id=settlement_json["id"],
                entry_type="refund",
                amount=amount,
                debit=amount,
                credit=Decimal("0"),
                fee=Decimal("0"),
                tax=Decimal("0"),
                payment_id=r["payment_id"],
                refund_id=r["id"],
                transfer_id=None,
                adjustment_id=None,
                order_id=None,
                settlement_utr=utr,
                description="Refund settlement",
                created_at=anchor,
                settled_at=None,
            )
        )

    status = settlement_json["status"]
    processed_at = None
    if status == "processed":
        anchors = list(payment_captured_at.values())
        processed_at = (max(anchors) if anchors else datetime(2026, 1, 1, tzinfo=timezone.utc)) + timedelta(days=1)

    settlement = RazorpaySettlement(
        settlement_id=settlement_json["id"],
        amount=total_amount,
        fees=total_fees,
        tax=Decimal("0"),
        utr=utr if status == "processed" else None,
        status=status,
        created_at=processed_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        processed_at=processed_at,
    )
    await repo.save_settlement(settlement)

    for entry in entries:
        entry.settled_at = processed_at
        await repo.save_settlement_entry(entry)

    return {
        "settlement_id": settlement.settlement_id,
        "utr": utr,
        "status": status,
        "razorpay_net": str(sum((e.credit - e.debit for e in entries), Decimal("0"))),
        "payments_created": len(created_payment_ids),
        "refunds_created": len(created_refund_ids),
        "settlement_entries_created": len(entries),
        "skipped_detail": skipped,
    }


def write_merchant_seeded(scenario_dir: Path, order_mapping: dict[str, str]) -> dict:
    src_dir = scenario_dir / "merchant_faulty"
    out_dir = scenario_dir / "merchant_seeded"
    out_dir.mkdir(exist_ok=True)

    written: list[str] = []
    skipped_empty: list[str] = []
    unmapped_order_refs: set[str] = set()

    # merchant_orders.csv (order_ref/date already alias to canonical fields;
    # currency is the one required field this dataset omits entirely).
    order_rows = list(csv.DictReader(open(src_dir / "merchant_orders.csv")))
    out_rows = []
    for row in order_rows:
        ref = row["razorpay_order_id"]
        real_id = order_mapping.get(ref, ref)  # intentionally-missing refs pass through untouched
        if ref not in order_mapping:
            unmapped_order_refs.add(ref)
        out_rows.append(
            {
                "merchant_order_id": row["order_ref"],
                "razorpay_order_id": real_id,
                "amount": row["amount"],
                "currency": "INR",
                "status": "paid",
                "created_at": row["date"],
            }
        )
    if out_rows:
        with (out_dir / "merchant_orders.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["merchant_order_id", "razorpay_order_id", "amount", "currency", "status", "created_at"])
            w.writeheader()
            w.writerows(out_rows)
        written.append("merchant_orders.csv")
    else:
        skipped_empty.append("merchant_orders.csv")

    # ledger.csv -- razorpay_payment_id preserved verbatim as `reference`;
    # this is the field G07/G11's entire fault lives in.
    ledger_rows = list(csv.DictReader(open(src_dir / "ledger.csv")))
    out_rows = [
        {
            "ledger_entry_id": f"LED-{scenario_dir.name.upper()}-{i:04d}",
            "merchant_order_id": row["order_ref"],
            "account_code": "SALES_REVENUE",
            "entry_type": "credit",
            "debit": "0.00",
            "credit": row["amount"],
            "currency": "INR",
            "posted_at": row["date"],
            "reference": row["razorpay_payment_id"],
            "description": row.get("notes") or "",
        }
        for i, row in enumerate(ledger_rows, start=1)
    ]
    if out_rows:
        with (out_dir / "ledger.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        written.append("ledger.csv")
    else:
        skipped_empty.append("ledger.csv")

    # bank_statement.csv -- only written when the source actually has rows;
    # an empty file is never submitted (see module docstring).
    bank_rows = list(csv.DictReader(open(src_dir / "bank_statement.csv")))
    out_rows = [
        {
            "transaction_id": f"BTX-{scenario_dir.name.upper()}-{i:04d}",
            "utr": row["utr"],
            "transaction_date": row["date"],
            "description": f"Settlement credit - {row['settlement_ref']}",
            "debit": "0.00",
            "credit": row["credited_amount"],
        }
        for i, row in enumerate(bank_rows, start=1)
    ]
    if out_rows:
        with (out_dir / "bank_statement.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        written.append("bank_statement.csv")
    else:
        skipped_empty.append("bank_statement.csv")

    # pos.csv / other_gateway.csv -- only G13 has rows.
    pos_rows = list(csv.DictReader(open(src_dir / "pos.csv")))
    out_rows = [
        {
            "pos_transaction_id": f"POS-{scenario_dir.name.upper()}-{i:04d}",
            "merchant_order_id": row["order_ref"],
            "amount": row["amount"],
            "currency": "INR",
            "transaction_date": row["date"],
            "status": "captured",
            "terminal_id": f"TERM-{scenario_dir.name.upper()}",
        }
        for i, row in enumerate(pos_rows, start=1)
    ]
    if out_rows:
        with (out_dir / "pos.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        written.append("pos.csv")
    else:
        skipped_empty.append("pos.csv")

    gw_rows = list(csv.DictReader(open(src_dir / "other_gateway.csv")))
    out_rows = [
        {
            "gateway_transaction_id": f"GTW-{scenario_dir.name.upper()}-{i:04d}",
            "merchant_order_id": row["order_ref"],
            "gateway_order_id": row["order_ref"],
            "amount": row["amount"],
            "currency": "INR",
            "status": "success",
            "created_at": row["date"],
        }
        for i, row in enumerate(gw_rows, start=1)
    ]
    if out_rows:
        with (out_dir / "other_gateway.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        written.append("other_gateway.csv")
    else:
        skipped_empty.append("other_gateway.csv")

    return {"written": written, "skipped_empty": skipped_empty, "unmapped_order_refs": sorted(unmapped_order_refs)}


async def run_scenario(scenario_dir: Path, use_case: CreateRazorpayOrderUseCase, db: PostgresConnection, repo: RazorpayPostgresRepository) -> dict:
    rzp = json.loads((scenario_dir / "razorpay.json").read_text())
    scenario_id = rzp["settlement"]["id"]
    bank_rows = list(csv.DictReader(open(scenario_dir / "merchant_faulty" / "bank_statement.csv")))

    order_mapping, order_report = await seed_orders(rzp["settlement"]["orders"], use_case, db)
    await correct_order_timestamps(rzp["settlement"]["orders"], order_mapping, db)
    settlement_summary = await seed_settlement_state(scenario_id, rzp, bank_rows, order_mapping, repo)
    csv_summary = write_merchant_seeded(scenario_dir, order_mapping)

    (scenario_dir / "order_mapping.json").write_text(json.dumps(order_report, indent=2))

    reused = sum(1 for r in order_report if r["reused"])
    return {
        "scenario": scenario_dir.name,
        "settlement_id": scenario_id,
        "orders_total": len(rzp["settlement"]["orders"]),
        "orders_created": len(order_report) - reused,
        "orders_reused": reused,
        **settlement_summary,
        "merchant_seeded": csv_summary,
    }


async def main() -> None:
    only = sys.argv[1:] or None

    db = PostgresConnection(DatabaseConfig(dsn=os.environ["DATABASE_URL"]))
    await db.connect()

    gateway = RazorpayApiGateway(key_id=os.environ["RAZORPAY_KEY_ID"], key_secret=os.environ["RAZORPAY_KEY_SECRET"])
    repo = RazorpayPostgresRepository(db)
    use_case = CreateRazorpayOrderUseCase(gateway=gateway, repository=repo)

    scenario_dirs = sorted(p for p in DATASET_ROOT.glob("scenario_g*") if p.is_dir())
    if only:
        scenario_dirs = [p for p in scenario_dirs if any(o in p.name for o in only)]

    results = []
    for scenario_dir in scenario_dirs:
        print(f"--- seeding {scenario_dir.name} ---", flush=True)
        result = await run_scenario(scenario_dir, use_case, db, repo)
        print(json.dumps(result, default=str), flush=True)
        results.append(result)

    (DATASET_ROOT / "golden_seed_report.json").write_text(json.dumps(results, indent=2, default=str))
    await db.close()

    print("\n=== SUMMARY ===")
    for r in results:
        print(r["scenario"], r["settlement_id"], "orders", r["orders_total"], f"(created {r['orders_created']}, reused {r['orders_reused']})")


if __name__ == "__main__":
    asyncio.run(main())
