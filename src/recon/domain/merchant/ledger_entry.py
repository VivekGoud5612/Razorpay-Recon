from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class LedgerEntry:
    entry_id: str
    merchant_order_id: str | None
    account_code: str
    entry_type: str
    debit: Decimal
    credit: Decimal
    currency: str
    posted_at: datetime
    reference: str | None
    description: str | None