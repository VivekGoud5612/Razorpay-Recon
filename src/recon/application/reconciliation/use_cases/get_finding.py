from __future__ import annotations

from recon.application.reconciliation.ports.result_repository import ReconciliationResultRepository
from recon.domain.reconciliation.finding import ReconciliationFinding


class GetFindingUseCase:

    def __init__(
        self,
        result_repository: ReconciliationResultRepository,
    ) -> None:
        self._result_repository = result_repository

    async def execute(
        self,
        settlement_id: str,
        finding_id: str,
    ) -> ReconciliationFinding:
        finding = await self._result_repository.get_finding(
            settlement_id,
            finding_id,
        )

        if finding is None:
            raise ValueError(
                f"Finding not found: {finding_id} (settlement={settlement_id})"
            )

        return finding
