from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RazorpayRefund:
    refund_id: str
    payment_id: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    processed_at: datetime | None