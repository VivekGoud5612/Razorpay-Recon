from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from recon.infrastructure.razorpay.gateway import RazorpayApiGateway


async def main() -> None:
    load_dotenv()

    gateway = RazorpayApiGateway(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )

    settlements = await gateway.fetch_settlements(
        count=100,
        skip=0,
    )

    print(f"settlements={len(settlements)}")

    for settlement in settlements:
        print(
            f"settlement_id={settlement.settlement_id} "
            f"amount={settlement.amount} "
            f"fees={settlement.fees} "
            f"tax={settlement.tax} "
            f"status={settlement.status} "
            f"utr={settlement.utr} "
            f"created_at={settlement.created_at}"
        )


if __name__ == "__main__":
    asyncio.run(main())