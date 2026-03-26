from fastapi import APIRouter, Depends, HTTPException

from app.core.permissions import ADMIN_ACCESS, has_permission
from app.dependencies import get_current_user
from app.models import User
from app.schemas import ForecastNextTicketOut, MlStatusOut
from app.services.ml_retraining import get_ml_status
from app.services.ticket_forecast import forecast_next_ticket_service


router = APIRouter(prefix="/ai", tags=["ai"])


def _ensure_ai_admin_access(current_user: User) -> None:
    if not has_permission(current_user, ADMIN_ACCESS):
        raise HTTPException(status_code=403, detail="AI-функции доступны только администраторам")


@router.get("/forecast-next-ticket", response_model=ForecastNextTicketOut)
async def forecast_next_ticket(
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_admin_access(current_user)
    return forecast_next_ticket_service()


@router.get("/status", response_model=MlStatusOut)
async def get_ai_status(
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_admin_access(current_user)
    return get_ml_status()
