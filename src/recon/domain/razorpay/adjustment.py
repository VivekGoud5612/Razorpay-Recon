from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RazorpayAdjustment:
    adjustment_id: str
    settlement_id: str
    amount: Decimal
    description: str | None
    created_at: datetime