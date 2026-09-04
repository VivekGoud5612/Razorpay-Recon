from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class InvestigateExceptionRequest:
    settlement_id: str
    finding_ids: list[str]