from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RazorpaySettlementEntry:
    entry_id: str
    settlement_id: str
    entry_type: str

    amount: Decimal
    debit: Decimal
    credit: Decimal
    fee: Decimal
    tax: Decimal

    payment_id: str | None
    refund_id: str | None
    transfer_id: str | None
    adjustment_id: str | None
    order_id: str | None

    settlement_utr: str | None
    description: str | None
    created_at: datetime
    settled_at: datetime | None