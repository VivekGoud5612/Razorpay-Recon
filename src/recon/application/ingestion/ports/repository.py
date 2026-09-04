from __future__ import annotations

from typing import Protocol, Any

from recon.domain.merchant.import_ import MerchantImport


class MerchantIngestionRepository(Protocol):

    async def create_import(
        self,
        merchant_import: MerchantImport,
    ) -> MerchantImport:
        ...

    async def persist_records(
        self,
        merchant_import: MerchantImport,
        entity_type: str,
        records: list[Any],
    ) -> None:
        ...

    async def complete_import(
        self,
        import_id: str,
        records_ingested: int,
    ) -> MerchantImport:
        ...

    async def fail_import(
        self,
        import_id: str,
    ) -> MerchantImport:
        ...