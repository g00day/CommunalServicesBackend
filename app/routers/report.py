from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TicketReportOut
from app.services.report import get_ticket_report_service


router = APIRouter(prefix="/report", tags=["report"])


@router.get("/tickets", response_model=TicketReportOut)
async def get_ticket_report(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_ticket_report_service(db, current_user, date_from, date_to)
