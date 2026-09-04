from __future__ import annotations

from recon.application.investigation.dto.evidence import EvidencePackage
from recon.application.investigation.dto.response import InvestigationResponse
from recon.application.investigation.ports.investigator import Investigator
from recon.application.investigation.services.investigation_policy import (
    InvestigationPolicy,
)


class InvestigationService:

    def __init__(
        self,
        investigator: Investigator,
        policy: InvestigationPolicy,
    ) -> None:
        self._investigator = investigator
        self._policy = policy

    async def investigate(
        self,
        evidence: EvidencePackage,
    ) -> InvestigationResponse:
        response = await self._investigator.investigate(evidence)

        return self._policy.validate(
            response,
            evidence,
        )