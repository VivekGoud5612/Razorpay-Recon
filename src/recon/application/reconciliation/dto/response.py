from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from recon.domain.reconciliation.evidence import EvidenceRef    
from recon.domain.reconciliation.finding import ReconciliationFinding


@dataclass(slots=True, frozen=True, kw_only=True)
class ReconcileSettlementResponse:
    settlement_id: str

    merchant_expected: Decimal
    razorpay_net: Decimal
    bank_observed: Decimal

    merchant_vs_razorpay_difference: Decimal
    razorpay_vs_bank_difference: Decimal

    status: str
    reason_code: str

    findings: list[ReconciliationFinding]
    evidence: list[EvidenceRef]



