from __future__ import annotations

from typing import Protocol

from recon.application.ingestion.dto.result import IngestionResult


class MerchantSourceAdapter(Protocol):
    def supports(
        self,
        filename: str,
        content_type: str,
    ) -> bool:
        ...

    def parse(self, content: bytes) -> list[dict[str, Any]]:
        ...