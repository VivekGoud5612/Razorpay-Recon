from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True, kw_only=True)
class IngestMerchantSourceResponse:
    import_id: str
    merchant_source_id: str
    status: str
    records_ingested: int