from typing import Annotated

from fastapi import APIRouter, Depends, File as FastAPIFile, Form, Header, HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas import (
    MessageOut,
    TicketOut,
    TicketStatusOut,
    TelegramBotCloseTicketRequest,
    TelegramBotMessageOut,
    TelegramBotStatusUpdateRequest,
    TelegramBotTicketDetailOut,
    TelegramBotTicketListItemOut,
    TelegramBotUserOut,
)
from app.services.telegram_bot import (
    close_bot_ticket_service,
    create_bot_message_service,
    get_bot_messages_service,
    get_bot_ticket_service,
    get_bot_ticket_statuses_service,
    get_bot_tickets_service,
    get_bot_user_service,
    update_bot_ticket_status_service,
)

router = APIRouter(prefix="/bot", tags=["telegram-bot-internal"])


def _validate_bot_secret(x_bot_secret: str | None) -> None:
    expected_secret = settings.TELEGRAM_BOT_INTERNAL_SECRET
    if not expected_secret:
        return
    if x_bot_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot secret")


@router.get("/me", response_model=TelegramBotUserOut)
async def get_bot_user(
    tg_chat_id: int,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await get_bot_user_service(db, tg_chat_id)


@router.get("/tickets", response_model=list[TelegramBotTicketListItemOut])
async def get_bot_tickets(
    tg_chat_id: int,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await get_bot_tickets_service(db, tg_chat_id)


@router.get("/tickets/{ticket_id}", response_model=TelegramBotTicketDetailOut)
async def get_bot_ticket(
    ticket_id: int,
    tg_chat_id: int,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await get_bot_ticket_service(db, ticket_id, tg_chat_id)


@router.get("/tickets/{ticket_id}/messages", response_model=list[TelegramBotMessageOut])
async def get_bot_messages(
    ticket_id: int,
    tg_chat_id: int,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await get_bot_messages_service(db, ticket_id, tg_chat_id)


@router.post("/tickets/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_bot_message(
    ticket_id: int,
    tg_chat_id: Annotated[int, Form(...)],
    text: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, FastAPIFile()] = None,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await create_bot_message_service(db, ticket_id, tg_chat_id, text, files or [])


@router.patch("/tickets/{ticket_id}/close", response_model=TicketOut)
async def close_bot_ticket(
    ticket_id: int,
    payload: TelegramBotCloseTicketRequest,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await close_bot_ticket_service(db, ticket_id, payload.tg_chat_id)


@router.patch("/tickets/{ticket_id}/status", response_model=TicketOut)
async def update_bot_ticket_status(
    ticket_id: int,
    payload: TelegramBotStatusUpdateRequest,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await update_bot_ticket_status_service(db, ticket_id, payload.tg_chat_id, payload.status_code)


@router.get("/ticket-statuses", response_model=list[TicketStatusOut])
async def get_bot_ticket_statuses(
    tg_chat_id: int,
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_bot_secret(x_bot_secret)
    return await get_bot_ticket_statuses_service(db, tg_chat_id)
