from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import TicketStatusOut
from app.services.ticket import get_ticket_statuses_service


router = APIRouter(prefix="/ticket-meta", tags=["ticket-reference"])


@router.get("/statuses", response_model=list[TicketStatusOut])
async def get_ticket_statuses(db: AsyncSession = Depends(get_db)):
    return await get_ticket_statuses_service(db)
