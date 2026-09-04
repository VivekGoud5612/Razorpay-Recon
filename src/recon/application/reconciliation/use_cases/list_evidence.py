from __future__ import annotations

from recon.application.reconciliation.ports.result_repository import ReconciliationResultRepository
from recon.domain.reconciliation.evidence import EvidenceRef


class ListEvidenceUseCase:

    def __init__(
        self,
        result_repository: ReconciliationResultRepository,
    ) -> None:
        self._result_repository = result_repository

    async def execute(
        self,
        settlement_id: str,
    ) -> list[EvidenceRef]:
        return await self._result_repository.list_evidence(settlement_id)
