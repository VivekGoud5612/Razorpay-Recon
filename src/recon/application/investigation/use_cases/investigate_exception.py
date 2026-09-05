from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import uuid4

from recon.application.investigation.dto.request import InvestigateExceptionRequest
from recon.application.investigation.dto.response import InvestigationResponse
from recon.application.investigation.ports.repository import InvestigationRepository
from recon.application.investigation.services.evidence_builder import EvidenceBuilder
from recon.application.investigation.services.investigation_service import InvestigationService


class InvestigateExceptionUseCase:

    def __init__(
        self,
        repository: InvestigationRepository,
        investigation_service: InvestigationService,
    ) -> None:
        self._repository = repository
        self._investigation_service = investigation_service

    async def execute(
        self,
        request: InvestigateExceptionRequest,
    ) -> InvestigationResponse:
        graph = await self._repository.get_graph(request.settlement_id)
        findings = await self._repository.get_findings(
            request.settlement_id,
            request.finding_ids,
        )

        finding_map = {finding.finding_id: finding for finding in findings}

        if len(finding_map) != len(request.finding_ids):
            raise ValueError("One or more findings were not found")

        selected_findings = [
            finding_map[finding_id]
            for finding_id in request.finding_ids
        ]

        package = await EvidenceBuilder(
            graph,
            self._repository,
            settlement_id=request.settlement_id,
        ).build(
            findings=selected_findings,
            depth=2,
        )

        response = await self._investigation_service.investigate(package)

        response = dataclasses.replace(
            response,
            investigation_id=f"inv_{uuid4().hex}",
            settlement_id=request.settlement_id,
            finding_ids=request.finding_ids,
            status="complete",
            created_at=datetime.now(timezone.utc),
        )

        await self._repository.save(response)

        return response