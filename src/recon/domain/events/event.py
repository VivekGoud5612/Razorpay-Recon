from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Event:
    event_id: str
    source: str
    event_type: str
    entity_type: str
    entity_id: str
    occurred_at: datetime
    received_at: datetime
    payload: dict[str, Any]