from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, Form

from recon.application.ingestion.dto.request import IngestMerchantSourceRequest
from recon.application.ingestion.dto.response import IngestMerchantSourceResponse
from recon.application.ingestion.use_cases.ingest_source import IngestMerchantSourceUseCase
from api.dependencies import get_ingestion_use_case

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

SOURCE_BY_FILENAME = {
    "merchant_orders.csv": "merchant_orders",
    "ledger.csv": "merchant_ledger",
    "pos.csv": "merchant_pos",
    "other_gateway.csv": "merchant_gateway",
    "bank_statement.csv": "merchant_bank",
}

@router.post("/merchant", response_model=IngestMerchantSourceResponse)
async def ingest_merchant_source(
    file: UploadFile = File(...),
    merchant_source_id: str = Form(...),
    use_case: IngestMerchantSourceUseCase = Depends(get_ingestion_use_case),
) -> IngestMerchantSourceResponse:
    content = await file.read()
    content_type = content_type=file.content_type or "application/octet-stream"

    request = IngestMerchantSourceRequest(
        merchant_source_id=merchant_source_id,
        filename=file.filename or "unknown",
        content_type=content_type,
        content=content,
    )

    return await use_case.execute(request)



@router.post("/merchant/batch")
async def ingest_merchant_sources(
    files: Annotated[list[UploadFile], File()],
    use_case: IngestMerchantSourceUseCase = Depends(get_ingestion_use_case),
) -> list[IngestMerchantSourceResponse]:
    responses = []

    for file in files:
        filename = file.filename or ""
        merchant_source_id = SOURCE_BY_FILENAME.get(filename)

        if merchant_source_id is None:
            raise ValueError(f"Unsupported merchant file: {filename}")

        content = await file.read()

        request = IngestMerchantSourceRequest(
            merchant_source_id=merchant_source_id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )

        responses.append(await use_case.execute(request))

    return responses