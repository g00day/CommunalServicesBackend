from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File as FastAPIFile, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TicketListItem, TicketOut, TicketStatusUpdate
from app.services.ml_retraining import register_new_ticket_for_retraining, run_retraining_pipeline
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
    background_tasks: BackgroundTasks,
    title: Annotated[str, Form(...)],
    address_id: Annotated[int, Form(...)],
    description: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, FastAPIFile()] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await create_ticket_service(
        db,
        current_user,
        title,
        address_id,
        description,
        files or [],
    )
    if register_new_ticket_for_retraining():
        background_tasks.add_task(run_retraining_pipeline)
    return ticket


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
