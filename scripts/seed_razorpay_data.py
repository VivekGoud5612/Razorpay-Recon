from __future__ import annotations

import asyncio
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from recon.application.razorpay.dto.requests import CreateOrderRequest
from recon.application.razorpay.use_cases.create_orders import CreateRazorpayOrderUseCase
from recon.infrastructure.persistence.postgres.config import DatabaseConfig
from recon.infrastructure.persistence.postgres.connection import PostgresConnection
from recon.infrastructure.persistence.postgres.razorpay_repository import RazorpayPostgresRepository
from recon.infrastructure.razorpay.gateway import RazorpayApiGateway


BASE_PATH = Path("/home/vivek/Downloads/razorpay_recon_additional_scenarios_51_plus")


def load_orders(path: Path) -> list[dict]:
    return json.loads(path.read_text())["orders"]


def load_merchant_orders(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_merchant_orders(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


async def seed_scenario(
    use_case: CreateRazorpayOrderUseCase,
    scenario_path: Path,
) -> None:
    orders = load_orders(scenario_path / "razorpay.json")
    merchant_orders_path = scenario_path / "merchant_faulty" / "merchant_orders.csv"
    merchant_orders = load_merchant_orders(merchant_orders_path)

    for merchant_order, order in zip(merchant_orders, orders):
        existing_id = merchant_order["razorpay_order_id"]

        if existing_id and existing_id.startswith("order_"):
            print(f"Skipping {merchant_order['merchant_order_id']}: {existing_id}")
            continue

        request = CreateOrderRequest(
            amount=order["amount"],
            currency=order["currency"],
            receipt=order["receipt"],
        )

        razorpay_order_id = await use_case.execute(request)
        merchant_order["razorpay_order_id"] = razorpay_order_id

        write_merchant_orders(
            merchant_orders_path,
            merchant_orders,
        )

        print(
            f"{merchant_order['merchant_order_id']} -> {razorpay_order_id}"
        )

        await asyncio.sleep(0.5)


async def main() -> None:
    load_dotenv()

    db = PostgresConnection(
        DatabaseConfig(dsn=os.getenv("DATABASE_URL"))
    )

    gateway = RazorpayApiGateway(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )

    repository = RazorpayPostgresRepository(db)

    use_case = CreateRazorpayOrderUseCase(
        gateway=gateway,
        repository=repository,
    )

    await db.connect()

    try:
        for scenario_path in sorted(BASE_PATH.iterdir()):
            if not scenario_path.is_dir():
                continue

            if not (scenario_path / "razorpay.json").exists():
                continue

            await seed_scenario(
                use_case,
                scenario_path,
            )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())