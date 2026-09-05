from __future__ import annotations

from typing import Any

from recon.application.investigation.dto.response import InvestigationResponse
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.reconciliation.finding import ReconciliationFinding


class InvestigationRepository:

    async def get_graph(self, settlement_id: str) -> ReconciliationGraph:
        raise NotImplementedError

    async def get_entity_record(
        self,
        source: str,
        entity_type: str,
        entity_id: str,
        settlement_id: str,
    ) -> dict[str, Any] | None:
        """Deterministic lookup of the persisted source record backing a
        single evidence/graph entity, scoped to exactly the entity named and
        to `settlement_id` -- no fuzzy matching, no scanning, and no
        possibility of resolving a different settlement's row when a
        merchant-world business id (e.g. "MORD-01") is reused across
        settlements. Returns None when the entity_type is unrecognized or no
        row matches.
        """
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
