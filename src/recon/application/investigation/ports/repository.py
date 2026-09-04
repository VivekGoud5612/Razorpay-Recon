from __future__ import annotations

from recon.application.investigation.dto.response import InvestigationResponse
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.reconciliation.finding import ReconciliationFinding


class InvestigationRepository:

    async def get_graph(self, settlement_id: str) -> ReconciliationGraph:
        raise NotImplementedError

    async def get_findings(
        self,
        settlement_id: str,
        finding_ids: list[str],
    ) -> list[ReconciliationFinding]:
        raise NotImplementedError

    async def save(
        self,
        response: InvestigationResponse,
    ) -> None:
        raise NotImplementedError

    async def get(
        self,
        investigation_id: str,
    ) -> InvestigationResponse | None:
        raise NotImplementedError
