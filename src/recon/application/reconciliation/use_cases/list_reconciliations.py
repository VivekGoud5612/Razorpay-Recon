from __future__ import annotations

from recon.application.reconciliation.dto.run import ReconciliationRunResponse
from recon.application.reconciliation.ports.result_repository import ReconciliationResultRepository


class ListReconciliationsUseCase:

    def __init__(
        self,
        result_repository: ReconciliationResultRepository,
    ) -> None:
        self._result_repository = result_repository

    async def execute(self) -> list[ReconciliationRunResponse]:
        return await self._result_repository.list_runs()
