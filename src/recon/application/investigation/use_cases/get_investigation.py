from __future__ import annotations

from recon.application.investigation.dto.response import InvestigationResponse
from recon.application.investigation.ports.repository import InvestigationRepository


class GetInvestigationUseCase:

    def __init__(
        self,
        repository: InvestigationRepository,
    ) -> None:
        self._repository = repository

    async def execute(
        self,
        investigation_id: str,
    ) -> InvestigationResponse:
        investigation = await self._repository.get(investigation_id)

        if investigation is None:
            raise ValueError(f"Investigation not found: {investigation_id}")

        return investigation
