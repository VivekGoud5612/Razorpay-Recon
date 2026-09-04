from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(slots=True, frozen=True, kw_only=True)
class PosTransaction:
    transaction_id: str
    merchant_order_id: str
    razorpay_order_id: str | None
    amount: Decimal
    currency: str
    transaction_date: date
    status: str
    terminal_id: str