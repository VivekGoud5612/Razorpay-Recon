from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class ReconciliationCase:
    case_id: str
    case_type: str
    settlement_id: str | None

    expected_amount: Decimal
    actual_amount: Decimal
    difference_amount: Decimal
    currency: str

    status: str
    reason_code: str | None

    created_at: datetime
    resolved_at: datetime | None