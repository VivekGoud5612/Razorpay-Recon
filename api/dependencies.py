from __future__ import annotations

from fastapi import Request

from recon.application.ingestion.use_cases.ingest_source import IngestMerchantSourceUseCase
from recon.application.investigation.use_cases.get_investigation import GetInvestigationUseCase
from recon.application.investigation.use_cases.investigate_exception import InvestigateExceptionUseCase
from recon.application.reconciliation.use_cases.get_finding import GetFindingUseCase
from recon.application.reconciliation.use_cases.get_graph import GetReconciliationGraphUseCase
from recon.application.reconciliation.use_cases.get_reconciliation import GetReconciliationUseCase
from recon.application.reconciliation.use_cases.list_evidence import ListEvidenceUseCase
from recon.application.reconciliation.use_cases.list_findings import ListFindingsUseCase
from recon.application.reconciliation.use_cases.list_reconciliations import ListReconciliationsUseCase
from recon.application.reconciliation.use_cases.reconcile_settlement import ReconcileSettlementUseCase


def get_ingestion_use_case(request: Request) -> IngestMerchantSourceUseCase:
    return request.app.state.ingestion_use_case


def get_reconciliation_use_case(request: Request) -> ReconcileSettlementUseCase:
    return request.app.state.reconciliation_use_case


def get_reconciliation_read_use_case(request: Request) -> GetReconciliationUseCase:
    return request.app.state.get_reconciliation_use_case


def list_reconciliations_use_case(request: Request) -> ListReconciliationsUseCase:
    return request.app.state.list_reconciliations_use_case


def list_findings_use_case(request: Request) -> ListFindingsUseCase:
    return request.app.state.list_findings_use_case


def get_finding_use_case(request: Request) -> GetFindingUseCase:
    return request.app.state.get_finding_use_case


def list_evidence_use_case(request: Request) -> ListEvidenceUseCase:
    return request.app.state.list_evidence_use_case


def get_reconciliation_graph_use_case(request: Request) -> GetReconciliationGraphUseCase:
    return request.app.state.get_reconciliation_graph_use_case


def get_investigation_use_case(request: Request) -> InvestigateExceptionUseCase:
    return request.app.state.investigation_use_case


def get_investigation_read_use_case(request: Request) -> GetInvestigationUseCase:
    return request.app.state.get_investigation_use_case
