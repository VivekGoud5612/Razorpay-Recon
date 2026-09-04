from __future__ import annotations

from dataclasses import dataclass 
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class MerchantImport:
    import_id: str
    source_id: str
    object_key: str
    filename: str
    content_type: str
    status: str
    records_ingested: int
    created_at: datetime
    completed_at: datetime | None