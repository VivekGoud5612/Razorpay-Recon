from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True, frozen=True, kw_only=True)
class ReconciliationRunResponse:
    settlement_id: str

    status: str
    reason_code: str

    merchant_expected: Decimal
    razorpay_net: Decimal
    bank_observed: Decimal

    merchant_vs_razorpay_difference: Decimal
    razorpay_vs_bank_difference: Decimal

    import_ids: list[str]
    created_at: datetime
    updated_at: datetime
