from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding


@dataclass(slots=True, frozen=True, kw_only=True)
class EvidenceDetail:
    """EvidenceRef plus, where available, the persisted source record it
    points to -- used by the Evidence Explorer so an evidence item can be
    traced deterministically back to its underlying record, not just its
    reference fields. Deliberately not folded into EvidenceRef itself:
    EvidenceRef is a domain value type used across reconciliation,
    persistence, and investigation; `data` is a read-side enrichment only
    the evidence-listing endpoint needs.
    """

    evidence_id: str
    source: str
    entity_type: str
    entity_id: str
    reason: str
    object_key: str | None
    data: dict[str, Any] | None


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



