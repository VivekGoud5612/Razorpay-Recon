from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RazorpaySettlement:
    settlement_id: str
    amount: Decimal
    fees: Decimal
    tax: Decimal
    utr: str | None
    status: str
    created_at: datetime
    processed_at: datetime | None