from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class ReconciliationResult:
    status: str
    expected_amount: Decimal
    actual_amount: Decimal
    difference_amount: Decimal
    reason_code: str
    evidence: list[EvidenceRef]