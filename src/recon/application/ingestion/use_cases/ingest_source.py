from __future__ import annotations

from datetime import datetime, timezone

from recon.application.ingestion.dto.request import IngestMerchantSourceRequest
from recon.application.ingestion.dto.response import IngestMerchantSourceResponse
from recon.application.ingestion.ports.object_storage import ObjectStorage
from recon.application.ingestion.ports.repository import MerchantIngestionRepository
from recon.application.ingestion.services.adapter_registry import MerchantSourceAdapterRegistry
from recon.application.ingestion.services.domain_constructor import MerchantDomainConstructor
from recon.application.ingestion.services.import_identity import ImportIdentityService
from recon.application.ingestion.services.normalizer import MerchantSourceNormalizer
from recon.application.ingestion.services.validator import MerchantRecordValidator
from recon.domain.merchant.import_ import MerchantImport


class IngestMerchantSourceUseCase:

    def __init__(
        self,
        adapter_registry: MerchantSourceAdapterRegistry,
        normalizer: MerchantSourceNormalizer,
        validator: MerchantRecordValidator,
        repository: MerchantIngestionRepository,
        domain_constructor: MerchantDomainConstructor,
        identity_service: ImportIdentityService,
        storage: ObjectStorage,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._normalizer = normalizer
        self._validator = validator
        self._repository = repository
        self._domain_constructor = domain_constructor
        self._identity_service = identity_service
        self._storage = storage

    async def execute(
        self,
        request: IngestMerchantSourceRequest,
    ) -> IngestMerchantSourceResponse:
        identity = self._identity_service.create(
            merchant_source_id=request.merchant_source_id,
            filename=request.filename,
        )

        merchant_import = await self._repository.create_import(
            self._build_merchant_import(request, identity)
        )

        try:
            await self._storage.put(
                identity.object_key,
                request.content,
                request.content_type,
            )

            adapter = self._adapter_registry.get_adapter(
                filename=request.filename,
                content_type=request.content_type,
            )

            raw_records = adapter.parse(request.content)
            normalization_result = self._normalizer.normalize(raw_records)

            errors = self._validator.validate(normalization_result)

            if errors:
                raise ValueError(f"Invalid merchant source: {errors}")

            domain_records = [
                self._domain_constructor.build(
                    normalization_result.entity_type,
                    record,
                )
                for record in normalization_result.records
            ]

            await self._repository.persist_records(
                merchant_import,
                normalization_result.entity_type,
                domain_records,
            )

            merchant_import = await self._repository.complete_import(
                merchant_import.import_id,
                len(domain_records),
            )

            return IngestMerchantSourceResponse(
                import_id=merchant_import.import_id,
                merchant_source_id=merchant_import.source_id,
                status=merchant_import.status,
                records_ingested=merchant_import.records_ingested,
            )

        except Exception:
            await self._repository.fail_import(
                merchant_import.import_id,
            )
            raise

    @staticmethod
    def _build_merchant_import(
        request: IngestMerchantSourceRequest,
        identity: ImportIdentity,
    ) -> MerchantImport:
        return MerchantImport(
            import_id=identity.import_id,
            source_id=request.merchant_source_id,
            object_key=identity.object_key,
            filename=request.filename,
            content_type=request.content_type,
            status="processing",
            records_ingested=0,
            created_at=datetime.now(timezone.utc),
            completed_at=None,
        )