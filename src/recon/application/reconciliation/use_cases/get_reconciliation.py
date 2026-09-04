from __future__ import annotations

from recon.application.reconciliation.dto.run import ReconciliationRunResponse
from recon.application.reconciliation.ports.result_repository import ReconciliationResultRepository


class GetReconciliationUseCase:

    def __init__(
        self,
        result_repository: ReconciliationResultRepository,
    ) -> None:
        self._result_repository = result_repository

    async def execute(
        self,
        settlement_id: str,
    ) -> ReconciliationRunResponse:
        run = await self._result_repository.get_run(settlement_id)

        if run is None:
            raise ValueError(
                f"Reconciliation not found for settlement: {settlement_id}"
            )

        return run
