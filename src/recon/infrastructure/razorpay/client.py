from __future__ import annotations

import razorpay


class RazorpayClient:
    def __init__(
        self,
        key_id: str,
        key_secret: str,
    ) -> None:
        self._client = razorpay.Client(
            auth=(key_id, key_secret),
        )

    def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: str | None = None,
    ) -> dict:
        data = {
            "amount": amount,
            "currency": currency,
        }

        if receipt is not None:
            data["receipt"] = receipt

        return self._client.order.create(data=data)

    def fetch_order(
        self,
        order_id: str,
    ) -> dict:
        return self._client.order.fetch(order_id)

    def fetch_orders(
        self,
        count: int = 10,
        skip: int = 0,
    ) -> dict:
        return self._client.order.all(
            {
                "count": count,
                "skip": skip,
            }
        )