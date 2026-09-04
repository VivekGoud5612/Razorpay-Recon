from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(slots=True)
class BankTransaction:
    transaction_id: str
    utr: str | None
    transaction_date: date
    value_date: date | None
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal | None
    reference: str | None