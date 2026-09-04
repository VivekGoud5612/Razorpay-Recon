from __future__ import annotations

from recon.application.reconciliation.ports.graph_repository import ReconciliationGraphRepository
from recon.domain.graph.graph import ReconciliationGraph


class GetReconciliationGraphUseCase:

    def __init__(
        self,
        graph_repository: ReconciliationGraphRepository,
    ) -> None:
        self._graph_repository = graph_repository

    async def execute(
        self,
        settlement_id: str,
    ) -> ReconciliationGraph:
        return await self._graph_repository.get(settlement_id)
