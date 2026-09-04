from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class MerchantSource:
    source_id: str
    merchant_id: str
    source_type: str
    name: str
    created_at: datetime