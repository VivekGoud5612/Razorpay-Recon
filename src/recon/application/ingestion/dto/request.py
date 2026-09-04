from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True, kw_only=True)
class IngestMerchantSourceRequest:
    merchant_source_id: str
    filename: str
    content_type: str
    content: bytes