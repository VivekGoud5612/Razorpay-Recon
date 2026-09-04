from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class Invoice:
    invoice_id: str
    merchant_order_id: str
    amount: Decimal
    currency: str
    status: str
    issued_at: datetime
    due_at: datetime | None