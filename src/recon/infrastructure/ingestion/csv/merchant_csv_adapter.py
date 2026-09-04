from __future__ import annotations

import io
import csv
from pathlib import Path
from typing import Any 

from recon.domain.merchant.order import MerchantOrder


class MerchantCsvAdapter:
    def supports(self, filename: str, content_type: str) -> bool:
        return Path(filename).suffix.lower() == ".csv" and (
            content_type in {"text/csv", "application/csv", "application/octet-stream", ""}
        )

    def parse(self, content: bytes) -> list[dict[str,Any]]:
        text = content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(text))

        return list(reader) 

            