from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from recon.domain.reconciliation.evidence import EvidenceRef


@dataclass(slots=True, frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    supporting_evidence_ids: list[str]
    confidence: float


@dataclass(slots=True, frozen=True)
class RootCause:
    hypothesis_id: str
    confidence: float


@dataclass(slots=True, frozen=True)
class InvestigationEvidence:
    evidence_id: str
    source: str
    entity_type: str
    entity_id: str
    reason: str
    data: dict[str, Any]
    object_key: str | None = None


@dataclass(slots=True, frozen=True)
class InvestigationResponse:
    factual_observations: list[str]
    hypotheses: list[Hypothesis]
    root_cause: RootCause | None
    evidence: list[InvestigationEvidence]
    missing_evidence: list[str]
    should_abstain: bool
    abstain_reason: str | None

    # Populated by InvestigateExceptionUseCase once the investigation
    # is persisted; empty when this is an in-flight/unpersisted response.
    investigation_id: str = ""
    settlement_id: str = ""
    finding_ids: list[str] = field(default_factory=list)
    status: str = "complete"
    created_at: datetime | None = None