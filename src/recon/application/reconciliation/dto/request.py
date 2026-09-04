from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ReconcileSettlementRequest:
    settlement_id: str
    import_ids: list[str]