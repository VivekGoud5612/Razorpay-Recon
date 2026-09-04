from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RazorpayPayment:
    payment_id: str
    order_id: str
    amount: Decimal
    currency: str
    status: str
    method: str | None
    fee: Decimal
    tax: Decimal
    created_at: datetime
    captured_at: datetime | None