from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class PaymentState:
    payment_id: str
    order_id: str | None
    status: str
    amount: Decimal
    last_event_id: str | None
    last_event_occurred_at: datetime | None
    updated_at: datetime