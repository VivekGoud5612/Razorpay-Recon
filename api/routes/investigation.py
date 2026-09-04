from fastapi import APIRouter, Depends

from recon.application.investigation.dto.request import InvestigateExceptionRequest
from recon.application.investigation.dto.response import InvestigationResponse
from recon.application.investigation.use_cases.get_investigation import GetInvestigationUseCase
from recon.application.investigation.use_cases.investigate_exception import InvestigateExceptionUseCase
from api.dependencies import get_investigation_read_use_case, get_investigation_use_case

router = APIRouter(prefix="/investigation", tags=["investigation"])


@router.post("/exceptions", response_model=InvestigationResponse)
async def investigate_exception(
    request: InvestigateExceptionRequest,
    use_case: InvestigateExceptionUseCase = Depends(get_investigation_use_case),
) -> InvestigationResponse:
    return await use_case.execute(request)


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: str,
    use_case: GetInvestigationUseCase = Depends(get_investigation_read_use_case),
) -> InvestigationResponse:
    return await use_case.execute(investigation_id)
