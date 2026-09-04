from __future__ import annotations

from recon.application.ingestion.ports.source_adapter import MerchantSourceAdapter


class MerchantSourceAdapterRegistry:
    def __init__(
        self,
        adapters: list[MerchantSourceAdapter],
    ) -> None:
        self._adapters = adapters

    def get_adapter(
        self,
        filename: str,
        content_type: str,
    ) -> MerchantSourceAdapter:
        for adapter in self._adapters:
            if adapter.supports(filename, content_type):
                return adapter

        raise ValueError(
            f"No source adapter supports "
            f"filename={filename!r}, content_type={content_type!r}"
        )