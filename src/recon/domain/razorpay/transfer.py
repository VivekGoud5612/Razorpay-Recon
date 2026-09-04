from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RazorpayTransfer:
    transfer_id: str
    payment_id: str
    amount: Decimal
    fee: Decimal
    tax: Decimal
    status: str
    created_at: datetime