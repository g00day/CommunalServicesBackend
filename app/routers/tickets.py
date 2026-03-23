from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TicketCreate, TicketListItem, TicketOut, TicketStatusUpdate
from app.services.ticket import (
    close_own_ticket_service,
    create_ticket_service,
    get_ticket_service,
    get_tickets_service,
    update_ticket_status_service,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_ticket_service(
        db,
        current_user,
        payload.title,
        payload.address_id,
        payload.description,
    )


@router.get("", response_model=list[TicketListItem])
async def get_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),):
    return await get_tickets_service(db, current_user)


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),):
    return await get_ticket_service(db, ticket_id, current_user)


@router.patch("/{ticket_id}/status", response_model=TicketOut)
async def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_ticket_status_service(
        db,
        ticket_id,
        payload.status_code,
        current_user,
    )


@router.patch("/{ticket_id}/close", response_model=TicketOut)
async def close_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await close_own_ticket_service(db, ticket_id, current_user)
