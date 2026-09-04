from __future__ import annotations

import asyncio
import os

from recon.application.razorpay.dto.requests import (
    CreateOrderRequest,
)
from recon.application.razorpay.use_cases.create_transaction import (
    CreateRazorpayTransactionUseCase,
)
from recon.infrastructure.persistence.postgres.config import DatabaseConfig
from recon.infrastructure.persistence.postgres.connection import (
    PostgresConnection,
)
from recon.infrastructure.persistence.postgres.razorpay_repository import (
    RazorpayPostgresRepository,
)
from recon.infrastructure.razorpay.gateway import RazorpayApiGateway


ORDERS = [
    CreateOrderRequest(
        amount=510000,
        currency="INR",
        receipt="scenario-36-001",
    ),
    CreateOrderRequest(
        amount=520000,
        currency="INR",
        receipt="scenario-36-002",
    ),
    CreateOrderRequest(
        amount=530000,
        currency="INR",
        receipt="scenario-36-003",
    ),
]


async def main() -> None:
    db = PostgresConnection(
        DatabaseConfig(
            dsn=os.environ["DATABASE_URL"],
        )
    )

    gateway = RazorpayApiGateway(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )

    repository = RazorpayPostgresRepository(db)

    use_case = CreateRazorpayTransactionUseCase(
        gateway=gateway,
        repository=repository,
    )

    await db.connect()

    try:
        for request in ORDERS:
            await use_case.execute(request)
            print(
                f"processed Razorpay order: "
                f"{request.receipt}"
            )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())