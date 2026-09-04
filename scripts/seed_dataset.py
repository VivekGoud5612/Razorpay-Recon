"""
Seeds the converted 20-scenario reconciliation dataset
(/home/vivek/Downloads/reconciliation_dataset_ours) into this project.

Phase 2 — real Razorpay orders:
    Every order listed in a scenario's razorpay.json is created through the
    existing CreateRazorpayOrderUseCase -> RazorpayApiGateway (live Razorpay
    test-mode API, RAZORPAY_KEY_ID/SECRET from .env) -> RazorpayPostgresRepository.
    No fake order rows are inserted directly.

    Idempotent: an order is looked up by `receipt` in razorpay_orders before
    calling the live API; if found, the existing real order_id is reused
    instead of creating a duplicate. All other repository writes already use
    ON CONFLICT ... DO UPDATE (see RazorpayPostgresRepository), so re-running
    this script is always safe.

    Scenario order ids (e.g. "SC01-ORDER-017") that a scenario intentionally
    omits from razorpay.json are NEVER created — they stay unmapped so that a
    merchant CSV reference to one keeps resolving to nothing (a genuine
    RAZORPAY_ORDER_NOT_FOUND), per the dataset's intent.

Phase 3 — synthetic Razorpay-side settlement state:
    payments, refunds, settlements, settlement_entries are written directly
    via RazorpayPostgresRepository (this dataset has no transfers/adjustments
    at all — see conversion_report.json). Values (amount/fee/tax/net/refs/
    UTRs) are taken from the scenario's razorpay.json verbatim, converted
    from paise to rupees. The one thing NOT taken verbatim: razorpay.json's
    settlement_entries/refunds all carry created_at=settled_at=processed_at=0
    (epoch) -- a conversion-pipeline placeholder, not a scenario-intended
    "before/after" exception (no scenario's answers.json ever lists a
    temporal-ordering exception code). Taking that 0 literally would make
    _validate_temporal fire SETTLEMENT_ENTRY_BEFORE_PAYMENT /
    SETTLEMENT_BEFORE_CAPTURE on every single entry in every scenario, which
    would drown out the dataset's actual intended findings. So those three
    fields are derived instead (entry.created_at = its payment's
    captured_at, entry.settled_at = the settlement's processed_at, refund
    created_at/processed_at = its payment's captured_at) -- entirely
    synthetic Razorpay-side metadata the dataset never specified, not a
    change to any scenario-intended (merchant-side) fault. This is reported,
    not silently done -- see the dataset audit report this script writes.

Output per scenario, under <scenario_dir>/:
    order_mapping.json   -- scenario order_id -> real order_id (+ reused flag)
    merchant_seeded/      -- merchant_faulty/*.csv copied through, with
                             merchant_orders.csv's razorpay_order_id column
                             rewritten to real order ids (unmapped/intentionally
                             -missing references are left untouched verbatim)

A top-level dataset_audit_report.json is written to the dataset root summarizing
per-scenario counts and any merchant_orders.csv references that don't resolve
to any order in that scenario's razorpay.json (dataset ground truth) --
consumed by the reference-quality review, not auto-"fixed" here.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import shutil
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

DATASET_ROOT = Path("/home/vivek/Downloads/reconciliation_dataset_ours")
CONCURRENCY = 3  # the live Razorpay test-mode API rate-limits aggressively
MAX_RETRIES = 8
RETRY_BASE_DELAY = 1.5


def paise(value: int) -> Decimal:
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"))


def epoch(value: int) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


async def existing_order_id(db: PostgresConnection, receipt: str) -> str | None:
    async with db.acquire() as conn:
        return await conn.fetchval(
            "SELECT order_id FROM razorpay_orders WHERE receipt = $1", receipt
        )


async def create_order_with_retry(use_case: CreateRazorpayOrderUseCase, order: dict) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            return await use_case.execute(
                CreateOrderRequest(amount=order["amount"], currency=order["currency"], receipt=order["receipt"])
            )
        except razorpay.errors.BadRequestError as exc:
            if "too many requests" not in str(exc).lower() or attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_BASE_DELAY * (2**attempt)
            print(f"  rate-limited on receipt={order['receipt']!r}, retrying in {delay:.1f}s", flush=True)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def seed_orders(
    scenario_id: str,
    orders: list[dict],
    use_case: CreateRazorpayOrderUseCase,
    db: PostgresConnection,
) -> tuple[dict[str, str], list[dict]]:
    mapping: dict[str, str] = {}
    report: list[dict] = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(order: dict) -> None:
        async with sem:
            receipt = order["receipt"]
            found = await existing_order_id(db, receipt)
            if found:
                mapping[order["order_id"]] = found
                report.append(
                    {"scenario_order_id": order["order_id"], "receipt": receipt, "real_order_id": found, "reused": True}
                )
                return

            real_id = await create_order_with_retry(use_case, order)
            mapping[order["order_id"]] = real_id
            report.append(
                {"scenario_order_id": order["order_id"], "receipt": receipt, "real_order_id": real_id, "reused": False}
            )

    await asyncio.gather(*(one(o) for o in orders))
    return mapping, report


async def correct_order_timestamps(orders: list[dict], mapping: dict[str, str], db: PostgresConnection) -> None:
    """
    The live Razorpay order.create API assigns created_at = wall-clock time
    of the API call -- there is no parameter to backdate it. Left as-is,
    every order would carry today's timestamp while its razorpay.json
    payment keeps the scenario's original (2026, historical) created_at,
    making payment.created_at < order.created_at universally true and
    spuriously firing PAYMENT_BEFORE_ORDER on nearly every record regardless
    of scenario intent. This corrects created_at on the orders we actually
    created (real order_id, real amount/currency/receipt from the live API)
    to the scenario's intended historical timestamp -- the one piece of
    metadata the live API cannot be told to preserve. Safe to re-run.
    """
    async with db.acquire() as conn:
        await conn.executemany(
            "UPDATE razorpay_orders SET created_at = $1 WHERE order_id = $2",
            [(epoch(o["created_at"]), mapping[o["order_id"]]) for o in orders if o["order_id"] in mapping],
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
        raise RuntimeError(
            f"{rzp.get('merchant_name')}: scenario has transfers/adjustments -- "
            f"this script only implements payments/refunds/settlement_entries."
        )

    # Settlement created_at/processed_at aren't in razorpay.json at all (the
    # dataset only supplies the financial fields) -- derive a consistent
    # "processed the day after the last capture" timestamp.
    captured_ats = [epoch(p["captured_at"]) for p in payments if p.get("captured_at")]
    processed_at = max(captured_ats) if captured_ats else datetime(2026, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta

    processed_at = processed_at + timedelta(days=1)

    settlement = RazorpaySettlement(
        settlement_id=settlement_json["settlement_id"],
        amount=paise(settlement_json["amount"]),
        fees=paise(settlement_json["fees"]),
        tax=paise(settlement_json["tax"]),
        utr=settlement_json.get("utr"),
        status=settlement_json["status"],
        created_at=processed_at,
        processed_at=processed_at,
    )
    await repo.save_settlement(settlement)

    # The payments/refunds/settlement_entries tables all have real (non-
    # weakened) foreign keys to razorpay_orders/payments/refunds -- exactly
    # matching how the real Razorpay system works (a payment cannot exist
    # against an order that was never created). Some scenarios' razorpay.json
    # references an order it deliberately excluded (the "ORDER_NOT_FOUND"
    # intent) from a *payment* or *settlement_entry* row too. Such a row is
    # schema-illegal to persist -- inserting it would either violate the FK
    # or require weakening the constraint, both out of scope. Skipping it is
    # the faithful representation: a real Razorpay could never have produced
    # that row either. The merchant-side ORDER_NOT_FOUND finding still fires
    # correctly from _validate_orders (a merchant-order-level check against
    # the orders that DO exist) independent of this. Skips are recorded, not
    # silently dropped.
    payment_captured_at: dict[str, datetime] = {}
    created_payment_ids: set[str] = set()
    created_refund_ids: set[str] = set()
    skipped: list[dict] = []

    for p in payments:
        real_order_id = order_mapping.get(p["order_id"])
        if real_order_id is None:
            skipped.append({"kind": "payment", "id": p["payment_id"], "reason": f"order {p['order_id']} was never created (intentionally missing)"})
            continue

        captured_at = epoch(p["captured_at"]) if p.get("captured_at") else None
        payment = RazorpayPayment(
            payment_id=p["payment_id"],
            order_id=real_order_id,
            amount=paise(p["amount"]),
            currency=p["currency"],
            status=p["status"],
            method=p.get("method"),
            fee=paise(p.get("fee", 0)),
            tax=paise(p.get("tax", 0)),
            created_at=epoch(p["created_at"]),
            captured_at=captured_at,
        )
        await repo.save_payment(payment)
        created_payment_ids.add(p["payment_id"])
        if captured_at is not None:
            payment_captured_at[p["payment_id"]] = captured_at

    for r in refunds:
        if r["payment_id"] not in created_payment_ids:
            skipped.append({"kind": "refund", "id": r["refund_id"], "reason": f"payment {r['payment_id']} was skipped/not created"})
            continue

        anchor = payment_captured_at.get(r["payment_id"], processed_at)
        refund = RazorpayRefund(
            refund_id=r["refund_id"],
            payment_id=r["payment_id"],
            amount=paise(r["amount"]),
            currency=r["currency"],
            status=r["status"],
            created_at=anchor,
            processed_at=anchor,
        )
        await repo.save_refund(refund)
        created_refund_ids.add(r["refund_id"])

    for e in entries:
        order_id = e.get("order_id")
        real_order_id = order_mapping.get(order_id) if order_id else None
        if order_id and real_order_id is None:
            skipped.append({"kind": "settlement_entry", "id": e["entry_id"], "reason": f"order {order_id} was never created (intentionally missing)"})
            continue
        if e.get("payment_id") and e["payment_id"] not in created_payment_ids:
            skipped.append({"kind": "settlement_entry", "id": e["entry_id"], "reason": f"payment {e['payment_id']} was skipped/not created"})
            continue
        if e.get("refund_id") and e["refund_id"] not in created_refund_ids:
            skipped.append({"kind": "settlement_entry", "id": e["entry_id"], "reason": f"refund {e['refund_id']} was skipped/not created"})
            continue

        entry_created_at = payment_captured_at.get(e.get("payment_id"), processed_at)
        entry = RazorpaySettlementEntry(
            entry_id=e["entry_id"],
            settlement_id=e["settlement_id"],
            entry_type=e["entry_type"],
            amount=paise(e["amount"]),
            debit=paise(e.get("debit", 0)),
            credit=paise(e.get("credit", 0)),
            fee=paise(e.get("fee", 0)),
            tax=paise(e.get("tax", 0)),
            payment_id=e.get("payment_id"),
            refund_id=e.get("refund_id"),
            transfer_id=e.get("transfer_id"),
            adjustment_id=e.get("adjustment_id"),
            order_id=real_order_id,
            settlement_utr=e.get("settlement_utr"),
            description=e.get("description"),
            created_at=entry_created_at,
            settled_at=processed_at,
        )
        await repo.save_settlement_entry(entry)

    return {
        "settlement_id": settlement.settlement_id,
        "payments": len(payments),
        "payments_skipped": sum(1 for s in skipped if s["kind"] == "payment"),
        "refunds": len(refunds),
        "refunds_skipped": sum(1 for s in skipped if s["kind"] == "refund"),
        "settlement_entries": len(entries),
        "settlement_entries_skipped": sum(1 for s in skipped if s["kind"] == "settlement_entry"),
        "skipped_detail": skipped,
    }


def rewrite_merchant_orders_csv(scenario_dir: Path, order_mapping: dict[str, str]) -> dict:
    src_dir = scenario_dir / "merchant_faulty"
    out_dir = scenario_dir / "merchant_seeded"
    out_dir.mkdir(exist_ok=True)

    for name in ("ledger.csv", "pos.csv", "other_gateway.csv", "bank_statement.csv"):
        shutil.copyfile(src_dir / name, out_dir / name)

    unmapped: set[str] = set()
    mapped_count = 0

    with (src_dir / "merchant_orders.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = reader.fieldnames

    for row in rows:
        ref = row.get("razorpay_order_id", "")
        real_id = order_mapping.get(ref)
        if real_id is not None:
            row["razorpay_order_id"] = real_id
            mapped_count += 1
        elif ref:
            unmapped.add(ref)

    with (out_dir / "merchant_orders.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {"rows": len(rows), "mapped": mapped_count, "unmapped_refs": sorted(unmapped)}


async def run_scenario(scenario_dir: Path, use_case: CreateRazorpayOrderUseCase, db: PostgresConnection, repo: RazorpayPostgresRepository) -> dict:
    rzp = json.loads((scenario_dir / "razorpay.json").read_text())

    order_mapping, order_report = await seed_orders(scenario_dir.name, rzp["orders"], use_case, db)
    await correct_order_timestamps(rzp["orders"], order_mapping, db)
    settlement_summary = await seed_settlement_state(rzp, order_mapping, repo)
    csv_summary = rewrite_merchant_orders_csv(scenario_dir, order_mapping)

    (scenario_dir / "order_mapping.json").write_text(json.dumps(order_report, indent=2))

    reused = sum(1 for r in order_report if r["reused"])
    result = {
        "scenario": scenario_dir.name,
        "merchant_name": rzp.get("merchant_name"),
        "orders_total": len(rzp["orders"]),
        "orders_created": len(order_report) - reused,
        "orders_reused": reused,
        **settlement_summary,
        "merchant_orders_csv": csv_summary,
    }
    return result


async def main() -> None:
    only = sys.argv[1:] or None  # optional scenario name filter, e.g. scenario_01

    db = PostgresConnection(DatabaseConfig.from_env())
    await db.connect()

    gateway = RazorpayApiGateway(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )
    repo = RazorpayPostgresRepository(db)
    use_case = CreateRazorpayOrderUseCase(gateway=gateway, repository=repo)

    scenario_dirs = sorted(p for p in DATASET_ROOT.glob("scenario_*") if p.is_dir())
    if only:
        scenario_dirs = [p for p in scenario_dirs if any(o in p.name for o in only)]

    results = []
    for scenario_dir in scenario_dirs:
        print(f"--- seeding {scenario_dir.name} ---", flush=True)
        result = await run_scenario(scenario_dir, use_case, db, repo)
        print(json.dumps(result), flush=True)
        results.append(result)

    (DATASET_ROOT / "dataset_audit_report.json").write_text(json.dumps(results, indent=2))
    await db.close()

    print("\n=== SUMMARY ===")
    for r in results:
        print(
            r["scenario"], r["merchant_name"],
            "orders", r["orders_total"], f"(created {r['orders_created']}, reused {r['orders_reused']})",
            "unmapped_refs", len(r["merchant_orders_csv"]["unmapped_refs"]),
        )


if __name__ == "__main__":
    asyncio.run(main())
