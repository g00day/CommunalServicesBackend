from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TicketListItem, TicketOut
from app.services.ticket import get_all_tickets_admin_service, get_ticket_admin_service


router = APIRouter(prefix="/admin/tickets", tags=["ticket-admin"])


@router.get("", response_model=list[TicketListItem])
async def get_all_tickets_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_all_tickets_admin_service(db, current_user)


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket_admin(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_ticket_admin_service(db, ticket_id, current_user)
