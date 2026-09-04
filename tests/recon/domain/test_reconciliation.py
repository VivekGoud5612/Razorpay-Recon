from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from recon.domain.reconciliation.case import ReconciliationCase
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.result import ReconciliationResult


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_reconciliation_case():
    case = ReconciliationCase(
        case_id="case_001",
        case_type="settlement_amount_mismatch",
        settlement_id="setl_001",
        expected_amount=Decimal("5000.00"),
        actual_amount=Decimal("4500.00"),
        difference_amount=Decimal("500.00"),
        currency="INR",
        status="open",
        reason_code="UNEXPLAINED_DIFFERENCE",
        created_at=NOW,
        resolved_at=None,
    )

    assert case.case_id == "case_001"
    assert case.settlement_id == "setl_001"
    assert case.expected_amount == Decimal("5000.00")
    assert case.actual_amount == Decimal("4500.00")
    assert case.difference_amount == Decimal("500.00")
    assert case.status == "open"


def test_evidence_ref():
    evidence = EvidenceRef(
        entity_type="adjustment",
        entity_id="adj_001",
        role="primary",
        reason="Matches unexplained settlement difference",
    )

    assert evidence.entity_type == "adjustment"
    assert evidence.entity_id == "adj_001"
    assert evidence.role == "primary"


def test_reconciliation_result():
    evidence = EvidenceRef(
        entity_type="settlement",
        entity_id="setl_001",
        role="primary",
        reason="Settlement record",
    )

    result = ReconciliationResult(
        status="reconciled",
        expected_amount=Decimal("5000.00"),
        actual_amount=Decimal("5000.00"),
        difference_amount=Decimal("0.00"),
        reason_code="EXACT_SETTLEMENT_MATCH",
        evidence=[evidence],
    )

    assert result.status == "reconciled"
    assert result.expected_amount == result.actual_amount
    assert result.difference_amount == Decimal("0.00")
    assert result.reason_code == "EXACT_SETTLEMENT_MATCH"
    assert len(result.evidence) == 1