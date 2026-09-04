from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class MerchantOrder:
    order_id: str
    amount: Decimal
    currency: str
    customer_ref: str | None
    invoice_id: str | None
    razorpay_order_id: str | None 
    status: str
    created_at: datetime