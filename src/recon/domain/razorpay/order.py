from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True, kw_only=True)
class RazorpayOrder:
    order_id: str
    amount: Decimal
    currency: str
    status: str
    receipt: str | None
    created_at: datetime