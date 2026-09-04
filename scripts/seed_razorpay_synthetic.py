from __future__ import annotations

import asyncio
import csv
import os
from decimal import Decimal
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


SCENARIOS_ROOT = Path(
    "/home/vivek/Downloads/razorpay_recon_additional_scenarios_51_plus"
)


FEE_RATE = Decimal("0.0236")
TAX_RATE = Decimal("0.18")


async def get_order_ids(
    scenario_dir: Path,
) -> list[str]:
    path = next(
        (
            scenario_dir / side / "merchant_orders.csv"
            for side in ("merchant_faulty", "merchant_clean")
            if (scenario_dir / side / "merchant_orders.csv").exists()
        ),
        None,
    )

    if path is None:
        raise FileNotFoundError(
            f"merchant_orders.csv not found in {scenario_dir}"
        )

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    return list({
        row["razorpay_order_id"]
        for row in rows
        if row.get("razorpay_order_id")
    })


async def seed_scenario(
    conn: asyncpg.Connection,
    scenario_id: int,
) -> None:
    matches = sorted(
        SCENARIOS_ROOT.glob(f"scenario_{scenario_id:02d}_*")
    )

    if not matches:
        print(f"Skipping scenario {scenario_id}: directory not found")
        return

    scenario_dir = matches[0]
    order_ids = await get_order_ids(scenario_dir)

    if not order_ids:
        print(f"Skipping scenario {scenario_id}: no orders")
        return

    rows = await conn.fetch(
        """
        SELECT
            order_id,
            amount,
            currency,
            created_at
        FROM razorpay_orders
        WHERE order_id = ANY($1::text[])
        ORDER BY created_at, order_id
        """,
        order_ids,
    )

    found = {row["order_id"] for row in rows}
    missing = sorted(set(order_ids) - found)

    if missing:
        raise ValueError(
            f"Scenario {scenario_id}: missing Razorpay orders: {missing}"
        )

    settlement_id = f"SETL-S{scenario_id:02d}-001"

    payment_rows = []

    for index, row in enumerate(rows, start=1):
        gross_amount = row["amount"]
        fee = (gross_amount * FEE_RATE).quantize(Decimal("0.01"))
        tax = (fee * TAX_RATE).quantize(Decimal("0.01"))
        net_amount = gross_amount - fee - tax

        payment_rows.append(
            (
                f"PAY-S{scenario_id:02d}-{index:03d}",
                row["order_id"],
                gross_amount,
                row["currency"],
                "captured",
                "card",
                fee,
                tax,
                net_amount,
                f"UTR-{scenario_id:02d}-{index:03d}",
            )
        )

    total_gross = sum(
        (row[2] for row in payment_rows),
        Decimal("0"),
    )

    total_fees = sum(
        (row[6] for row in payment_rows),
        Decimal("0"),
    )

    total_tax = sum(
        (row[7] for row in payment_rows),
        Decimal("0"),
    )

    total_net = sum(
        (row[8] for row in payment_rows),
        Decimal("0"),
    )

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO settlements (
                settlement_id,
                amount,
                fees,
                tax,
                utr,
                status,
                created_at,
                processed_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                'processed',
                now(),
                now()
            )
            ON CONFLICT (settlement_id)
            DO UPDATE SET
                amount = EXCLUDED.amount,
                fees = EXCLUDED.fees,
                tax = EXCLUDED.tax,
                utr = EXCLUDED.utr,
                status = EXCLUDED.status,
                created_at = EXCLUDED.created_at,
                processed_at = EXCLUDED.processed_at
            """,
            settlement_id,
            total_net,
            total_fees,
            total_tax,
            f"SETTLE-UTR-{scenario_id:02d}-001",
        )

        await conn.executemany(
            """
            INSERT INTO payments (
                payment_id,
                order_id,
                amount,
                currency,
                status,
                method,
                fee,
                tax,
                created_at,
                captured_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                now(),
                now()
            )
            ON CONFLICT (payment_id)
            DO UPDATE SET
                order_id = EXCLUDED.order_id,
                amount = EXCLUDED.amount,
                currency = EXCLUDED.currency,
                status = EXCLUDED.status,
                method = EXCLUDED.method,
                fee = EXCLUDED.fee,
                tax = EXCLUDED.tax,
                created_at = EXCLUDED.created_at,
                captured_at = EXCLUDED.captured_at
            """,
            [
                (
                    payment_id,
                    order_id,
                    gross_amount,
                    currency,
                    status,
                    method,
                    fee,
                    tax,
                )
                for (
                    payment_id,
                    order_id,
                    gross_amount,
                    currency,
                    status,
                    method,
                    fee,
                    tax,
                    _net_amount,
                    _utr,
                ) in payment_rows
            ],
        )

        entry_rows = [
            (
                payment_id,
                settlement_id,
                gross_amount,
                fee,
                tax,
                payment_id,
                order_id,
                utr,
            )
            for (
                payment_id,
                order_id,
                gross_amount,
                _currency,
                _status,
                _method,
                fee,
                tax,
                _net_amount,
                utr,
            ) in payment_rows
        ]

        await conn.executemany(
            """
            INSERT INTO settlement_entries (
                entry_id,
                settlement_id,
                entry_type,
                amount,
                debit,
                credit,
                fee,
                tax,
                payment_id,
                refund_id,
                transfer_id,
                adjustment_id,
                order_id,
                settlement_utr,
                description,
                created_at,
                settled_at
            )
            VALUES (
                $1,
                $2,
                'payment',
                $3,
                0,
                $3::numeric - $4::numeric - $5::numeric,
                $4,
                $5,
                $6,
                NULL,
                NULL,
                NULL,
                $7,
                $8,
                'Payment settlement',
                now(),
                now()
            )
            ON CONFLICT (entry_id)
            DO UPDATE SET
                settlement_id = EXCLUDED.settlement_id,
                entry_type = EXCLUDED.entry_type,
                amount = EXCLUDED.amount,
                debit = EXCLUDED.debit,
                credit = EXCLUDED.credit,
                fee = EXCLUDED.fee,
                tax = EXCLUDED.tax,
                payment_id = EXCLUDED.payment_id,
                refund_id = EXCLUDED.refund_id,
                transfer_id = EXCLUDED.transfer_id,
                adjustment_id = EXCLUDED.adjustment_id,
                order_id = EXCLUDED.order_id,
                settlement_utr = EXCLUDED.settlement_utr,
                description = EXCLUDED.description,
                created_at = EXCLUDED.created_at,
                settled_at = EXCLUDED.settled_at
            """,
            entry_rows,
        )

    print(
        f"Scenario {scenario_id}: "
        f"{len(rows)} orders → "
        f"{len(payment_rows)} payments → "
        f"{settlement_id} → "
        f"net {total_net}"
    )


async def main() -> None:
    load_dotenv()

    conn = await asyncpg.connect(
        os.environ["DATABASE_URL"]
    )

    try:
        for scenario_id in range(51,81):
            await seed_scenario(conn, scenario_id)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())