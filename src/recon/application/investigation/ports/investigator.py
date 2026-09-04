from __future__ import annotations

from typing import Protocol

from recon.application.investigation.dto.evidence import EvidencePackage
from recon.application.investigation.dto.response import InvestigationResponse


class Investigator(Protocol):

    async def investigate(
        self,
        evidence: EvidencePackage,
    ) -> InvestigationResponse:
        ...