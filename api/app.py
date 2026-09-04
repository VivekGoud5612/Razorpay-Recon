from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.ingestion import router as ingestion_router
from api.routes.reconciliation import router as reconciliation_router
from api.routes.investigation import router as investigation_router

from recon.application.ingestion.services.adapter_registry import MerchantSourceAdapterRegistry
from recon.application.ingestion.services.domain_constructor import MerchantDomainConstructor
from recon.application.ingestion.services.import_identity import ImportIdentityService
from recon.application.ingestion.services.normalizer import MerchantSourceNormalizer
from recon.application.ingestion.services.validator import MerchantRecordValidator
from recon.application.ingestion.use_cases.ingest_source import IngestMerchantSourceUseCase

from recon.application.reconciliation.services.graph_builder import ReconciliationGraphBuilder
from recon.application.reconciliation.services.reconciliation_service import ReconcileSettlementService
from recon.application.reconciliation.use_cases.get_finding import GetFindingUseCase
from recon.application.reconciliation.use_cases.get_graph import GetReconciliationGraphUseCase
from recon.application.reconciliation.use_cases.get_reconciliation import GetReconciliationUseCase
from recon.application.reconciliation.use_cases.list_evidence import ListEvidenceUseCase
from recon.application.reconciliation.use_cases.list_findings import ListFindingsUseCase
from recon.application.reconciliation.use_cases.list_reconciliations import ListReconciliationsUseCase
from recon.application.reconciliation.use_cases.reconcile_settlement import ReconcileSettlementUseCase

from recon.application.investigation.services.investigation_policy import InvestigationPolicy
from recon.application.investigation.services.investigation_service import InvestigationService
from recon.application.investigation.use_cases.get_investigation import GetInvestigationUseCase
from recon.application.investigation.use_cases.investigate_exception import InvestigateExceptionUseCase

from recon.infrastructure.ai.huggingface_client import HuggingFaceLLMClient
from recon.infrastructure.investigation.investigator import LLMInvestigator
from recon.infrastructure.investigation.mcp.document_tools import DocumentTools
from recon.infrastructure.persistence.postgres.connection import PostgresConnection
from recon.infrastructure.persistence.postgres.config import DatabaseConfig

from recon.infrastructure.persistence.postgres.repositories.ingestion_repository import MerchantIngestionPostgresRepository
from recon.infrastructure.persistence.postgres.repositories.reconciliation_repository import ReconcileSettlementPostgresRepository
from recon.infrastructure.persistence.postgres.repositories.graph_repository import ReconciliationPostgresGraphRepository
from recon.infrastructure.persistence.postgres.repositories.reconciliation_result_repository import ReconciliationPostgresResultRepository
from recon.infrastructure.persistence.postgres.repositories.investigation_repository import InvestigationPostgresRepository

from recon.infrastructure.storage.minio.object_storage import MinioObjectStorage
from recon.infrastructure.ingestion.csv.merchant_csv_adapter import MerchantCsvAdapter

# Origins the frontend dev server(s) run on. Override with a comma-separated
# list via CORS_ALLOW_ORIGINS for other setups (e.g. a deployed frontend).
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()

    db = PostgresConnection(
        DatabaseConfig(
            dsn=os.environ["DATABASE_URL"],
        ),
    )
    await db.connect()

    storage = MinioObjectStorage(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        bucket_name=os.environ["MINIO_BUCKET"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    storage.ensure_bucket()

    ingestion_repository = MerchantIngestionPostgresRepository(db)
    reconciliation_repository = ReconcileSettlementPostgresRepository(db)
    graph_repository = ReconciliationPostgresGraphRepository(db)
    result_repository = ReconciliationPostgresResultRepository(db)
    investigation_repository = InvestigationPostgresRepository(db)

    ingestion_use_case = IngestMerchantSourceUseCase(
        adapter_registry=MerchantSourceAdapterRegistry(
            adapters = [
                MerchantCsvAdapter(),
            ]
        ),
        normalizer=MerchantSourceNormalizer(),
        validator=MerchantRecordValidator(),
        repository=ingestion_repository,
        domain_constructor=MerchantDomainConstructor(),
        identity_service=ImportIdentityService(),
        storage=storage,
    )

    reconciliation_use_case = ReconcileSettlementUseCase(
        repository=reconciliation_repository,
        result_repository=result_repository,
        service=ReconcileSettlementService(),
        graph_builder=ReconciliationGraphBuilder(),
        graph_repository=graph_repository,
    )

    get_reconciliation_use_case = GetReconciliationUseCase(result_repository)
    list_reconciliations_use_case = ListReconciliationsUseCase(result_repository)
    list_findings_use_case = ListFindingsUseCase(result_repository)
    get_finding_use_case = GetFindingUseCase(result_repository)
    list_evidence_use_case = ListEvidenceUseCase(result_repository)
    get_reconciliation_graph_use_case = GetReconciliationGraphUseCase(graph_repository)

    llm_client = HuggingFaceLLMClient(
        api_key=os.environ["HF_TOKEN"],
        model=os.environ["HF_MODEL"],
    )

    document_tools = DocumentTools(storage)

    investigator = LLMInvestigator(
        client=llm_client,
        document_tools=document_tools,
    )

    investigation_service = InvestigationService(
        investigator=investigator,
        policy=InvestigationPolicy(),
    )

    investigation_use_case = InvestigateExceptionUseCase(
        repository=investigation_repository,
        investigation_service=investigation_service,
    )

    get_investigation_use_case = GetInvestigationUseCase(investigation_repository)

    app.state.db = db
    app.state.storage = storage

    app.state.ingestion_use_case = ingestion_use_case
    app.state.reconciliation_use_case = reconciliation_use_case
    app.state.get_reconciliation_use_case = get_reconciliation_use_case
    app.state.list_reconciliations_use_case = list_reconciliations_use_case
    app.state.list_findings_use_case = list_findings_use_case
    app.state.get_finding_use_case = get_finding_use_case
    app.state.list_evidence_use_case = list_evidence_use_case
    app.state.get_reconciliation_graph_use_case = get_reconciliation_graph_use_case
    app.state.investigation_use_case = investigation_use_case
    app.state.get_investigation_use_case = get_investigation_use_case

    yield

    await db.close()


app = FastAPI(
    title="Razorpay Finance Reconciliation",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
        if _cors_origins_env
        else DEFAULT_CORS_ORIGINS
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # Most ValueErrors raised by use cases/repositories are lookup failures
    # ("Settlement not found", "Import not found", ...) -> 404. Anything
    # else (e.g. ingestion record validation) is a client input problem -> 400.
    status_code = 404 if "not found" in str(exc).lower() else 400
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


app.include_router(ingestion_router)
app.include_router(reconciliation_router)
app.include_router(investigation_router)
