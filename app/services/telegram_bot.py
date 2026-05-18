from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import TICKETS_READ_ALL, TICKETS_UPDATE_STATUS, has_permission
from app.core.storage import generate_download_url
from app.models import Address, Message, Role, Ticket, TicketStatus, User
from app.schemas import (
    MessageFileOut,
    TicketStatusOut,
    TelegramBotMessageOut,
    TelegramBotTicketDetailOut,
    TelegramBotTicketListItemOut,
    TelegramBotUserOut,
)
from app.services.ticket import (
    _build_ticket_out,
    close_own_ticket_service,
    get_all_tickets_admin_service,
    get_ticket_service,
    get_ticket_statuses_service,
    get_tickets_service,
    update_ticket_status_service,
)
from app.services.ticket_chat import create_message_service


async def _get_user_by_tg_chat_id(db: AsyncSession, tg_chat_id: int) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.tg_chat_id == tg_chat_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Telegram-чат не привязан к аккаунту")
    if not user.is_activated:
        raise HTTPException(status_code=403, detail="Аккаунт деактивирован")
    return user


def _address_label(ticket: Ticket) -> str | None:
    if not ticket.address:
        return None
    street_name = ticket.address.street.name if ticket.address.street else "Улица"
    return f"{street_name} {ticket.address.house_number}"


async def get_bot_user_service(db: AsyncSession, tg_chat_id: int) -> TelegramBotUserOut:
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    return TelegramBotUserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_admin=has_permission(user, "admin.access"),
        can_manage_tickets=has_permission(user, TICKETS_UPDATE_STATUS),
        tg_chat_id=user.tg_chat_id or tg_chat_id,
    )


async def get_bot_tickets_service(db: AsyncSession, tg_chat_id: int) -> list[TelegramBotTicketListItemOut]:
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    items = await (get_all_tickets_admin_service(db, user) if has_permission(user, TICKETS_READ_ALL) else get_tickets_service(db, user))

    tickets_by_id = {}
    if items:
        result = await db.execute(
            select(Ticket)
            .options(
                selectinload(Ticket.address).selectinload(Address.street),
                selectinload(Ticket.creator),
            )
            .where(Ticket.id.in_([item.id for item in items]))
        )
        tickets_by_id = {ticket.id: ticket for ticket in result.scalars().all()}

    return [
        TelegramBotTicketListItemOut(
            id=item.id,
            title=item.title,
            status=item.status,
            opened_at=item.opened_at,
            is_closed=item.is_closed,
            address_label=_address_label(tickets_by_id.get(item.id)) if tickets_by_id.get(item.id) else None,
        )
        for item in items
    ]


async def get_bot_ticket_service(db: AsyncSession, ticket_id: int, tg_chat_id: int) -> TelegramBotTicketDetailOut:
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    ticket_out = await get_ticket_service(db, ticket_id, user)
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.address).selectinload(Address.street),
            selectinload(Ticket.creator),
        )
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one()
    return TelegramBotTicketDetailOut(
        id=ticket_out.id,
        title=ticket_out.title,
        description=ticket_out.description,
        status=ticket_out.status,
        opened_at=ticket_out.opened_at,
        closed_at=ticket_out.closed_at,
        is_closed=ticket_out.is_closed,
        creator_name=ticket.creator.full_name,
        address_label=_address_label(ticket),
    )


async def get_bot_messages_service(db: AsyncSession, ticket_id: int, tg_chat_id: int) -> list[TelegramBotMessageOut]:
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    await get_ticket_service(db, ticket_id, user)

    result = await db.execute(
        select(Message)
        .where(Message.chat.has(ticket_id=ticket_id))
        .order_by(Message.sent_at)
    )
    messages = result.scalars().all()

    items: list[TelegramBotMessageOut] = []
    for message in messages:
        files = [
            MessageFileOut(
                id=file_item.id,
                message_id=file_item.message_id,
                file_url=await generate_download_url(file_item.file_url, file_item.file_path),
                file_name=file_item.file_name,
                mime_type=file_item.mime_type,
                uploaded_at=file_item.uploaded_at,
            )
            for file_item in message.files
        ]
        items.append(
            TelegramBotMessageOut(
                id=message.id,
                sender_user_id=message.sender_user_id,
                sender_name=message.sender.full_name,
                text=message.text,
                sent_at=message.sent_at,
                files=files,
            )
        )
    return items


async def create_bot_message_service(
    db: AsyncSession,
    ticket_id: int,
    tg_chat_id: int,
    text: str | None,
    files: list[UploadFile] | None = None,
):
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    return await create_message_service(db, ticket_id, text, user, files or [])


async def close_bot_ticket_service(db: AsyncSession, ticket_id: int, tg_chat_id: int):
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    return await close_own_ticket_service(db, ticket_id, user)


async def update_bot_ticket_status_service(
    db: AsyncSession,
    ticket_id: int,
    tg_chat_id: int,
    status_code: str,
):
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    return await update_ticket_status_service(db, ticket_id, status_code, user)


async def get_bot_ticket_statuses_service(db: AsyncSession, tg_chat_id: int) -> list[TicketStatusOut]:
    user = await _get_user_by_tg_chat_id(db, tg_chat_id)
    if not has_permission(user, TICKETS_UPDATE_STATUS):
        raise HTTPException(status_code=403, detail="Недостаточно прав для смены статуса")
    return await get_ticket_statuses_service(db)
