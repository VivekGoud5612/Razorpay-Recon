from __future__ import annotations

from recon.domain.graph.graph import ReconciliationGraph


class ReconciliationGraphRepository:

    async def save(
        self,
        settlement_id: str,
        graph: ReconciliationGraph,
    ) -> None:
        raise NotImplementedError

    async def get(
        self,
        settlement_id: str,
    ) -> ReconciliationGraph:
        raise NotImplementedError
