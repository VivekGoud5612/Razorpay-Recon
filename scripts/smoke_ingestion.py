from __future__ import annotations

import asyncio
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv

from recon.application.ingestion.dto.request import (
    IngestMerchantSourceRequest,
)
from recon.application.ingestion.services.adapter_registry import (
    MerchantSourceAdapterRegistry,
)
from recon.application.ingestion.services.domain_constructor import (
    MerchantDomainConstructor,
)
from recon.application.ingestion.services.import_identity import (
    ImportIdentityService,
)
from recon.application.ingestion.services.normalizer import (
    MerchantSourceNormalizer,
)
from recon.application.ingestion.services.validator import (
    MerchantRecordValidator,
)
from recon.infrastructure.ingestion.csv.merchant_csv_adapter import (
    MerchantCsvAdapter,
)
from recon.infrastructure.persistence.postgres.connection import (
    PostgresConnection,
)
from recon.infrastructure.persistence.postgres.ingestion_repository import (
    MerchantIngestionPostgresRepository,
)
from recon.infrastructure.storage.minio.object_storage import (
    MinioObjectStorage,
)

from recon.infrastructure.persistence.postgres.config import DatabaseConfig

load_dotenv()

SCENARIO_DIR = Path(
    "/home/vivek/Downloads/razorpay_recon_scenarios/"
    "scenario_36_rounding_difference"
)

SOURCE_ID = "src_demo_001"

MINIO_ENDPOINT = os.environ.get(
    "MINIO_ENDPOINT",
    "localhost:9000",
)
MINIO_ACCESS_KEY = os.environ.get(
    "MINIO_ACCESS_KEY",
    "recon_minio",
)
MINIO_SECRET_KEY = os.environ.get(
    "MINIO_SECRET_KEY",
    "recon_minio_dev_only",
)
MINIO_BUCKET = os.environ.get(
    "MINIO_BUCKET",
    "recon-files",
)


def build_use_case() -> tuple[
    object,
    PostgresConnection,
    MinioObjectStorage,
]:
    # Infrastructure implementations
    db = PostgresConnection(
        DatabaseConfig(
            dsn=os.environ["DATABASE_URL"],
        )
    )

    repository = MerchantIngestionPostgresRepository(db)

    storage = MinioObjectStorage(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name=MINIO_BUCKET,
        secure=False,
    )

    # Application services
    registry = MerchantSourceAdapterRegistry(
        adapters=[
            MerchantCsvAdapter(),
        ],
    )

    normalizer = MerchantSourceNormalizer()
    validator = MerchantRecordValidator()
    constructor = MerchantDomainConstructor()
    identity_service = ImportIdentityService()

    from recon.application.ingestion.use_cases.ingest_source import (
        IngestMerchantSourceUseCase,
    )

    use_case = IngestMerchantSourceUseCase(
        adapter_registry=registry,
        normalizer=normalizer,
        validator=validator,
        repository=repository,
        domain_constructor=constructor,
        identity_service=identity_service,
        storage=storage,
    )

    return use_case, db, storage


async def ingest_file(
    use_case,
    file_path: Path,
) -> None:
    content = file_path.read_bytes()

    content_type, _ = mimetypes.guess_type(
        file_path.name,
    )

    if content_type is None:
        content_type = "text/csv"

    request = IngestMerchantSourceRequest(
        merchant_source_id=SOURCE_ID,
        filename=file_path.name,
        content_type=content_type,
        content=content,
    )

    response = await use_case.execute(request)

    print(
        f"{file_path.name}: "
        f"{response.status} | "
        f"import_id={response.import_id} | "
        f"records={response.records_ingested}"
    )


async def main() -> None:
    use_case, db, storage = build_use_case()

    await db.connect()

    try:
        storage.ensure_bucket()

        csv_files = sorted(
            SCENARIO_DIR.glob("*.csv"),
        )

        if not csv_files:
            raise FileNotFoundError(
                f"No CSV files found in {SCENARIO_DIR}"
            )

        for file_path in csv_files:
            await ingest_file(
                use_case,
                file_path,
            )

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())