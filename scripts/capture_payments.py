from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from recon.infrastructure.razorpay.gateway import RazorpayApiGateway


BASE_PATH = Path(
    "/home/vivek/Downloads/razorpay_recon_50_scenarios"
)


def load_order_ids(scenario_path: Path) -> list[str]:
    import csv

    path = scenario_path / "merchant_faulty" / "merchant_orders.csv"

    with path.open("r", newline="", encoding="utf-8") as file:
        return [
            row["razorpay_order_id"]
            for row in csv.DictReader(file)
            if row.get("razorpay_order_id")
        ]


async def verify_scenario(
    gateway: RazorpayApiGateway,
    scenario_path: Path,
) -> tuple[int, int]:

    order_ids = load_order_ids(scenario_path)

    total = 0
    captured = 0

    print(f"\n=== {scenario_path.name} ===")

    for order_id in order_ids:
        if not order_id.startswith("order_"):
            print(f"{order_id} -> INVALID ORDER ID")
            continue

        total += 1

        payments = await gateway.fetch_order_payments(order_id)

        if not payments:
            print(f"{order_id} -> NO PAYMENTS")
            continue

        for payment in payments:
            if payment.status == "authorized":
                print(
                    f"{order_id} -> "
                    f"{payment.payment_id} -> AUTHORIZED -> CAPTURING"
                )

                await gateway.capture_payment(
                    payment_id=payment.payment_id,
                    amount=payment.amount,
                    currency=payment.currency,
                )

                payments = await gateway.fetch_order_payments(order_id)

            for payment in payments:
                print(
                    f"{order_id} -> "
                    f"{payment.payment_id} -> "
                    f"status={payment.status} "
                    f"captured={payment.captured}"
                )

                if payment.status == "captured":
                    captured += 1
                    break

    print(
        f"Scenario summary: "
        f"{captured}/{total} orders have captured payments"
    )

    return total, captured


async def main() -> None:
    load_dotenv()

    gateway = RazorpayApiGateway(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )

    grand_total = 0
    grand_captured = 0

    for scenario_number in range(1, 11):
        scenario_path = next(
            BASE_PATH.glob(
                f"scenario_{scenario_number:02d}_*/"
            ),
            None,
        )

        if scenario_path is None:
            print(
                f"\nScenario {scenario_number:02d}: "
                f"directory not found"
            )
            continue

        total, captured = await verify_scenario(
            gateway,
            scenario_path,
        )

        grand_total += total
        grand_captured += captured

    print("\n=== FINAL SUMMARY ===")
    print(f"Orders checked: {grand_total}")
    print(f"Orders with captured payments: {grand_captured}")

    if grand_total == grand_captured:
        print("ALL PAYMENTS CAPTURED")
    else:
        print(
            f"UNCAPTURED: "
            f"{grand_total - grand_captured}"
        )


if __name__ == "__main__":
    asyncio.run(main())