from fastapi import APIRouter, Depends, Query

from app.core.uow import AppUnitOfWork
from app.features.finances.schemas import FinanceSummaryResponse
from app.features.finances.service import FinancesService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access

router = APIRouter(prefix="/api/v1/finances", tags=["finances"])


@router.get("/summary", response_model=FinanceSummaryResponse)
async def get_finance_summary(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    months: int = Query(12, ge=1, le=60),
    date_from: str | None = Query(None, description="Start date, format YYYY-MM-DD"),
    date_to: str | None = Query(None, description="End date, format YYYY-MM-DD"),
):
    service = FinancesService(uow)

    return await service.get_summary(
        org_id=org_id, months=months, date_from=date_from, date_to=date_to
    )
