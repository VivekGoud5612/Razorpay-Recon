"""
Seeds the rich_recon_60 scenario (datasets/razorpay_recon_rich_dataset,
settlement SETL-RICH-001) through the same real, production application
paths as the other datasets -- no fake order-creation path, no direct
fabrication of what CreateRazorpayOrderUseCase is supposed to produce.

This dataset's razorpay.json is already close to the app's real shape
(settlement amount/fees/tax/utr in paise, orders/payments/settlement_entries
as separate lists, settlement_entries carrying their own settlement_utr) --
much closer than the golden-16 dataset's minimal schema. Two things still
need real Razorpay orders and a derived, ingestible merchant_seeded/:

1. razorpay_order_id values in razorpay.json/merchant_orders.csv are
   placeholders ("RICH-ORDER-0001"...), not real Razorpay ids -- every one
   is created for real via CreateRazorpayOrderUseCase, idempotently (looked
   up first by `receipt` = the placeholder id itself, a stable, unique,
   deterministic reference -- orders are never mapped by row position).
2. pos.csv/other_gateway.csv use a generic `transaction_id` header; the
   real ingestion normalizer requires `pos_transaction_id`/
   `gateway_transaction_id` specifically (confirmed live: as-is, pos.csv's
   generic `transaction_id` even causes the entity detector to misclassify
   the file as merchant_order, since razorpay_order_id also appears in
   pos.csv). merchant_orders.csv/ledger.csv/bank_statement.csv already use
   the exact columns the app expects and are carried through unchanged
   except for the razorpay_order_id remap.

Nothing about which rows exist, what they claim, or the five controlled
anomalies (README.md / answers.json) is altered -- only the two
ingestibility-blocking issues above, in the derived merchant_seeded/ copy.
datasets/razorpay_recon_rich_dataset/merchant/ is never modified.

Payments/settlement/settlement_entries are written directly via
RazorpayPostgresRepository (as scripts/seed_dataset.py already does for the
other real-Razorpay-shaped dataset) since the live Razorpay test-mode API
has no way to fabricate settlement events on demand -- these are taken from
razorpay.json verbatim (paise -> rupees), with order_id/payment_id
references remapped through the real-order mapping built in step 1.

Idempotent: safe to re-run from a clean merchant-ingestion state (orders
reused by receipt; payments/refunds/settlement/settlement_entries are
upserts in the repository already).
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
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

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets" / "razorpay_recon_rich_dataset"
CONCURRENCY = 3
MAX_RETRIES = 8
RETRY_BASE_DELAY = 1.5


def rupees(paise) -> Decimal:
    return (Decimal(paise) / Decimal(100)).quantize(Decimal("0.01"))


def paise_from_rupees(value) -> int:
    return int((Decimal(str(value)) * 100).to_integral_value())


def to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


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
                    currency=order["currency"],
                    receipt=order["razorpay_order_id"],
                )
            )
        except razorpay.errors.BadRequestError as exc:
            if "too many requests" not in str(exc).lower() or attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_BASE_DELAY * (2**attempt)
            print(f"  rate-limited on receipt={order['razorpay_order_id']!r}, retrying in {delay:.1f}s", flush=True)
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
            receipt = order["razorpay_order_id"]
            found = await existing_order_id(db, receipt)
            if found:
                mapping[receipt] = found
                report.append({"placeholder_order_id": receipt, "real_order_id": found, "reused": True})
                return

            real_id = await create_order_with_retry(use_case, order)
            mapping[receipt] = real_id
            report.append({"placeholder_order_id": receipt, "real_order_id": real_id, "reused": False})

    await asyncio.gather(*(one(o) for o in orders))
    return mapping, report


async def correct_order_timestamps(orders: list[dict], mapping: dict[str, str], db: PostgresConnection) -> None:
    async with db.acquire() as conn:
        await conn.executemany(
            "UPDATE razorpay_orders SET created_at = $1 WHERE order_id = $2",
            [(to_datetime(o["created_at"]), mapping[o["razorpay_order_id"]]) for o in orders if o["razorpay_order_id"] in mapping],
        )


async def seed_settlement_state(
    rzp: dict,
    order_mapping: dict[str, str],
    repo: RazorpayPostgresRepository,
) -> dict:
    settlement_json = rzp["settlement"]
    payments = rzp.get("payments", [])
    refunds = rzp.get("refunds", [])
    entries = rzp.get("settlement_entries", [])

    if rzp.get("transfers") or rzp.get("adjustments"):
        raise RuntimeError("rich_recon_60: transfers/adjustments present but not implemented by this script")

    settlement = RazorpaySettlement(
        settlement_id=settlement_json["settlement_id"],
        amount=rupees(settlement_json["amount"]),
        fees=rupees(settlement_json["fees"]),
        tax=rupees(settlement_json["tax"]),
        utr=settlement_json.get("utr"),
        status=settlement_json["status"],
        created_at=to_datetime(payments[0]["created_at"]) if payments else datetime(2026, 1, 1, tzinfo=timezone.utc),
        processed_at=to_datetime(max(p["captured_at"] for p in payments if p.get("captured_at"))) if payments else None,
    )
    await repo.save_settlement(settlement)

    created_payment_ids: set[str] = set()
    created_refund_ids: set[str] = set()
    skipped: list[dict] = []

    for p in payments:
        real_order_id = order_mapping.get(p["order_id"])
        if real_order_id is None:
            skipped.append({"kind": "payment", "id": p["payment_id"], "reason": f"order {p['order_id']} was never created"})
            continue

        payment = RazorpayPayment(
            payment_id=p["payment_id"],
            order_id=real_order_id,
            amount=rupees(p["amount"]),
            currency=p["currency"],
            status=p["status"],
            method=p.get("method"),
            fee=rupees(p.get("fee", 0)),
            tax=rupees(p.get("tax", 0)),
            created_at=to_datetime(p["created_at"]),
            captured_at=to_datetime(p["captured_at"]) if p.get("captured_at") else None,
        )
        await repo.save_payment(payment)
        created_payment_ids.add(p["payment_id"])

    for r in refunds:
        if r["payment_id"] not in created_payment_ids:
            skipped.append({"kind": "refund", "id": r["refund_id"], "reason": f"payment {r['payment_id']} was skipped/not created"})
            continue

        refund = RazorpayRefund(
            refund_id=r["refund_id"],
            payment_id=r["payment_id"],
            amount=rupees(r["amount"]),
            currency=r["currency"],
            status=r["status"],
            created_at=to_datetime(r["created_at"]),
            processed_at=to_datetime(r["processed_at"]) if r.get("processed_at") else None,
        )
        await repo.save_refund(refund)
        created_refund_ids.add(r["refund_id"])

    for e in entries:
        order_id = e.get("order_id")
        real_order_id = order_mapping.get(order_id) if order_id else None
        if order_id and real_order_id is None:
            skipped.append({"kind": "settlement_entry", "id": e["entry_id"], "reason": f"order {order_id} was never created"})
            continue
        if e.get("payment_id") and e["payment_id"] not in created_payment_ids:
            skipped.append({"kind": "settlement_entry", "id": e["entry_id"], "reason": f"payment {e['payment_id']} was skipped/not created"})
            continue
        if e.get("refund_id") and e["refund_id"] not in created_refund_ids:
            skipped.append({"kind": "settlement_entry", "id": e["entry_id"], "reason": f"refund {e['refund_id']} was skipped/not created"})
            continue

        entry = RazorpaySettlementEntry(
            entry_id=e["entry_id"],
            settlement_id=e["settlement_id"],
            entry_type=e["entry_type"],
            amount=rupees(e["amount"]),
            debit=rupees(e.get("debit", 0)),
            credit=rupees(e.get("credit", 0)),
            fee=rupees(e.get("fee", 0)),
            tax=rupees(e.get("tax", 0)),
            payment_id=e.get("payment_id"),
            refund_id=e.get("refund_id"),
            transfer_id=e.get("transfer_id"),
            adjustment_id=e.get("adjustment_id"),
            order_id=real_order_id,
            settlement_utr=e.get("settlement_utr"),
            description=e.get("description"),
            created_at=to_datetime(e["created_at"]),
            settled_at=to_datetime(e["settled_at"]) if e.get("settled_at") else None,
        )
        await repo.save_settlement_entry(entry)

    return {
        "settlement_id": settlement.settlement_id,
        "payments": len(payments),
        "payments_skipped": sum(1 for s in skipped if s["kind"] == "payment"),
        "refunds": len(refunds),
        "settlement_entries": len(entries),
        "settlement_entries_skipped": sum(1 for s in skipped if s["kind"] == "settlement_entry"),
        "skipped_detail": skipped,
    }


def write_merchant_seeded(order_mapping: dict[str, str]) -> dict:
    src_dir = DATASET_DIR / "merchant"
    out_dir = DATASET_DIR / "merchant_seeded"
    out_dir.mkdir(exist_ok=True)

    written: list[str] = []
    unmapped: set[str] = set()

    # merchant_orders.csv: columns already match the real ingestion
    # contract exactly -- only razorpay_order_id needs remapping to a real
    # Razorpay order id.
    rows = list(csv.DictReader(open(src_dir / "merchant_orders.csv")))
    for row in rows:
        ref = row["razorpay_order_id"]
        real_id = order_mapping.get(ref)
        if real_id is not None:
            row["razorpay_order_id"] = real_id
        else:
            unmapped.add(ref)
    with (out_dir / "merchant_orders.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    written.append("merchant_orders.csv")

    # ledger.csv: columns already match exactly; copied through verbatim.
    import shutil
    shutil.copyfile(src_dir / "ledger.csv", out_dir / "ledger.csv")
    written.append("ledger.csv")

    # bank_statement.csv: columns already match exactly; copied through
    # verbatim (UTRs are untouched -- they already agree exactly with
    # razorpay.json's settlement_entries[].settlement_utr).
    shutil.copyfile(src_dir / "bank_statement.csv", out_dir / "bank_statement.csv")
    written.append("bank_statement.csv")

    # pos.csv: rename the generic `transaction_id` header to
    # `pos_transaction_id` (see module docstring) and remap
    # razorpay_order_id like merchant_orders.csv. Everything else verbatim.
    rows = list(csv.DictReader(open(src_dir / "pos.csv")))
    out_rows = []
    for row in rows:
        new_row = {("pos_transaction_id" if k == "transaction_id" else k): v for k, v in row.items()}
        ref = new_row.get("razorpay_order_id")
        if ref:
            new_row["razorpay_order_id"] = order_mapping.get(ref, ref)
        out_rows.append(new_row)
    with (out_dir / "pos.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    written.append("pos.csv")

    # other_gateway.csv: same rename, to `gateway_transaction_id`. No
    # razorpay_order_id column here to remap.
    rows = list(csv.DictReader(open(src_dir / "other_gateway.csv")))
    out_rows = [
        {("gateway_transaction_id" if k == "transaction_id" else k): v for k, v in row.items()}
        for row in rows
    ]
    with (out_dir / "other_gateway.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    written.append("other_gateway.csv")

    return {"written": written, "unmapped_razorpay_order_ids": sorted(unmapped)}


async def main() -> None:
    db = PostgresConnection(DatabaseConfig(dsn=os.environ["DATABASE_URL"]))
    await db.connect()

    gateway = RazorpayApiGateway(key_id=os.environ["RAZORPAY_KEY_ID"], key_secret=os.environ["RAZORPAY_KEY_SECRET"])
    repo = RazorpayPostgresRepository(db)
    use_case = CreateRazorpayOrderUseCase(gateway=gateway, repository=repo)

    rzp = json.loads((DATASET_DIR / "razorpay.json").read_text())

    print("--- seeding rich_recon_60 / SETL-RICH-001 ---", flush=True)
    order_mapping, order_report = await seed_orders(rzp["orders"], use_case, db)
    await correct_order_timestamps(rzp["orders"], order_mapping, db)
    settlement_summary = await seed_settlement_state(rzp, order_mapping, repo)
    csv_summary = write_merchant_seeded(order_mapping)

    (DATASET_DIR / "order_mapping.json").write_text(json.dumps(order_report, indent=2))

    reused = sum(1 for r in order_report if r["reused"])
    result = {
        "orders_total": len(rzp["orders"]),
        "orders_created": len(order_report) - reused,
        "orders_reused": reused,
        **settlement_summary,
        "merchant_seeded": csv_summary,
    }
    print(json.dumps(result, indent=2, default=str))

    (DATASET_DIR / "rich_seed_report.json").write_text(json.dumps(result, indent=2, default=str))
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
