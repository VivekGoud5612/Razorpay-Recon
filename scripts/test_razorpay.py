from __future__ import annotations

import os
from dotenv import load_dotenv

from recon.infrastructure.razorpay.client import RazorpayClient
load_dotenv()

def main() -> None:
    client = RazorpayClient(
        key_id=os.getenv("RAZORPAY_KEY_ID"),
        key_secret=os.getenv("RAZORPAY_KEY_SECRET"),
    )

    order = client.create_order(
        amount=50000,
        currency="INR",
        receipt="recon-test-001",
    )

    print(order)


if __name__ == "__main__":
    main()