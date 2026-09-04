from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True, frozen=True, kw_only=True)
class GatewayTransaction:
    transaction_id: str
    merchant_order_id: str
    gateway_order_id: str
    amount: Decimal
    currency: str
    fee: Decimal
    tax: Decimal
    status: str
    created_at: datetime