from __future__ import annotations

from recon.application.reconciliation.dto.response import ReconcileSettlementResponse
from recon.application.reconciliation.dto.run import ReconciliationRunResponse
from recon.domain.reconciliation.finding import ReconciliationFinding
from recon.domain.reconciliation.evidence import EvidenceRef

class ReconciliationResultRepository:

    async def save(
        self,
        settlement_id: str,
        findings: list[ReconciliationFinding],
        evidence: list[EvidenceRef],
    ) -> None:
        raise NotImplementedError

    async def save_run(
        self,
        response: ReconcileSettlementResponse,
        import_ids: list[str],
    ) -> None:
        raise NotImplementedError

    async def get_run(
        self,
        settlement_id: str,
    ) -> ReconciliationRunResponse | None:
        raise NotImplementedError

    async def list_runs(self) -> list[ReconciliationRunResponse]:
        raise NotImplementedError

    async def list_findings(
        self,
        settlement_id: str,
    ) -> list[ReconciliationFinding]:
        raise NotImplementedError

    async def get_finding(
        self,
        settlement_id: str,
        finding_id: str,
    ) -> ReconciliationFinding | None:
        raise NotImplementedError

    async def list_evidence(
        self,
        settlement_id: str,
    ) -> list[EvidenceRef]:
        raise NotImplementedError
