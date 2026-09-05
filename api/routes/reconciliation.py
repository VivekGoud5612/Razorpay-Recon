from fastapi import APIRouter, Depends

from recon.application.reconciliation.dto.graph import GraphResponse
from recon.application.reconciliation.dto.request import ReconcileSettlementRequest
from recon.application.reconciliation.dto.response import EvidenceDetail, ReconcileSettlementResponse
from recon.application.reconciliation.dto.run import ReconciliationRunResponse
from recon.application.reconciliation.use_cases.get_finding import GetFindingUseCase
from recon.application.reconciliation.use_cases.get_graph import GetReconciliationGraphUseCase
from recon.application.reconciliation.use_cases.get_reconciliation import GetReconciliationUseCase
from recon.application.reconciliation.use_cases.list_evidence import ListEvidenceUseCase
from recon.application.reconciliation.use_cases.list_findings import ListFindingsUseCase
from recon.application.reconciliation.use_cases.list_reconciliations import ListReconciliationsUseCase
from recon.application.reconciliation.use_cases.reconcile_settlement import ReconcileSettlementUseCase
from recon.domain.reconciliation.finding import ReconciliationFinding

from api.dependencies import (
    get_finding_use_case,
    get_reconciliation_graph_use_case,
    get_reconciliation_use_case,
    get_reconciliation_read_use_case,
    list_evidence_use_case,
    list_findings_use_case,
    list_reconciliations_use_case,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post("/settlements", response_model=ReconcileSettlementResponse)
async def reconcile_settlement(
    request: ReconcileSettlementRequest,
    use_case: ReconcileSettlementUseCase = Depends(get_reconciliation_use_case),
) -> ReconcileSettlementResponse:
    return await use_case.execute(request)


@router.get("/settlements", response_model=list[ReconciliationRunResponse])
async def list_reconciliations(
    use_case: ListReconciliationsUseCase = Depends(list_reconciliations_use_case),
) -> list[ReconciliationRunResponse]:
    return await use_case.execute()


@router.get("/settlements/{settlement_id}", response_model=ReconciliationRunResponse)
async def get_reconciliation(
    settlement_id: str,
    use_case: GetReconciliationUseCase = Depends(get_reconciliation_read_use_case),
) -> ReconciliationRunResponse:
    return await use_case.execute(settlement_id)


@router.get(
    "/settlements/{settlement_id}/findings",
    response_model=list[ReconciliationFinding],
)
async def list_findings(
    settlement_id: str,
    use_case: ListFindingsUseCase = Depends(list_findings_use_case),
) -> list[ReconciliationFinding]:
    return await use_case.execute(settlement_id)


@router.get(
    "/settlements/{settlement_id}/findings/{finding_id}",
    response_model=ReconciliationFinding,
)
async def get_finding(
    settlement_id: str,
    finding_id: str,
    use_case: GetFindingUseCase = Depends(get_finding_use_case),
) -> ReconciliationFinding:
    return await use_case.execute(settlement_id, finding_id)


@router.get(
    "/settlements/{settlement_id}/evidence",
    response_model=list[EvidenceDetail],
)
async def list_evidence(
    settlement_id: str,
    use_case: ListEvidenceUseCase = Depends(list_evidence_use_case),
) -> list[EvidenceDetail]:
    return await use_case.execute(settlement_id)


@router.get(
    "/settlements/{settlement_id}/graph",
    response_model=GraphResponse,
)
async def get_graph(
    settlement_id: str,
    use_case: GetReconciliationGraphUseCase = Depends(get_reconciliation_graph_use_case),
) -> GraphResponse:
    graph = await use_case.execute(settlement_id)

    return GraphResponse(
        nodes=list(graph.nodes.values()),
        edges=list(graph.edges.values()),
    )
