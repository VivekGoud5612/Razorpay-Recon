from __future__ import annotations

from typing import Protocol

from recon.application.reconciliation.dto.data import SettlementReconciliationData


class ReconcileSettlementRepository(Protocol):

    async def get_settlement_context(
        self,
        settlement_id: str,
        import_ids: list[str],
    ) -> SettlementReconciliationData:
        ...