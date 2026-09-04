from __future__ import annotations

from recon.application.reconciliation.dto.request import ReconcileSettlementRequest
from recon.application.reconciliation.dto.response import ReconcileSettlementResponse
from recon.application.reconciliation.ports.graph_repository import ReconciliationGraphRepository
from recon.application.reconciliation.ports.repository import ReconcileSettlementRepository
from recon.application.reconciliation.ports.result_repository import ReconciliationResultRepository
from recon.application.reconciliation.services.reconciliation_service import ReconcileSettlementService
from recon.application.reconciliation.services.graph_builder import ReconciliationGraphBuilder


class ReconcileSettlementUseCase:

    def __init__(
        self,
        repository: ReconcileSettlementRepository,
        result_repository: ReconciliationResultRepository,
        service: ReconcileSettlementService,
        graph_builder: ReconciliationGraphBuilder,
        graph_repository: ReconciliationGraphRepository,
    ) -> None:
        self.repository = repository
        self.result_repository = result_repository
        self.reconciliation_service = service
        self.graph_builder = graph_builder
        self.graph_repository = graph_repository

    async def execute(
        self,
        request: ReconcileSettlementRequest,
    ) -> ReconcileSettlementResponse:
        data = await self.repository.get_settlement_context(
            settlement_id=request.settlement_id,
            import_ids=request.import_ids,
        )

        response = self.reconciliation_service.reconcile(data)

        await self.result_repository.save_run(
            response=response,
            import_ids=request.import_ids,
        )

        if response.status == "exception":
            graph = self.graph_builder.build(data=data, response=response)

            await self.graph_repository.save(
                settlement_id=response.settlement_id,
                graph=graph,
            )

            await self.result_repository.save(
                settlement_id=response.settlement_id,
                findings=response.findings,
                evidence=response.evidence,
            )

        return response