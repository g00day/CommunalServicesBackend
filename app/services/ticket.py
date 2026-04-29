from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import (
    TICKETS_READ_ALL,
    TICKETS_UPDATE_STATUS,
    has_any_permission,
    has_permission,
)
from app.core.storage import generate_download_url, upload_file_to_storage
from app.models import Address, Chat, ChatParticipant, Ticket, TicketFile, TicketStatus, User
from app.schemas import TicketListItem, TicketOut, TicketStatusOut
from app.services.audit import write_audit_log

CREATED_STATUS_CODE = "created"
CLOSED_STATUS_CODE = "closed"
FINAL_STATUS_CODES = {"completed", "closed", "rejected"}
STAFF_TICKET_PERMISSIONS = (TICKETS_READ_ALL, TICKETS_UPDATE_STATUS)


def _is_staff(user: User) -> bool:
  return has_any_permission(user, *STAFF_TICKET_PERMISSIONS)


def _can_access_ticket(user: User, ticket: Ticket) -> bool:
  return has_permission(user, TICKETS_READ_ALL) or ticket.user_id == user.id


def _ensure_ticket_read_all(user: User) -> None:
  if not has_permission(user, TICKETS_READ_ALL):
    raise HTTPException(status_code=403, detail="Просмотр всех заявок требует отдельного права")


async def _get_status_by_code(db: AsyncSession, code: str) -> TicketStatus:
  result = await db.execute(select(TicketStatus).where(TicketStatus.code == code))
  ticket_status = result.scalar_one_or_none()
  if not ticket_status:
    raise HTTPException(status_code=404, detail="Статус заявки не найден")
  return ticket_status


async def _get_ticket_by_id(db: AsyncSession, ticket_id: int) -> Ticket:
  result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
  ticket = result.scalar_one_or_none()
  if not ticket:
    raise HTTPException(status_code=404, detail="Заявка не найдена")
  return ticket


async def _ensure_address_exists(db: AsyncSession, address_id: int) -> Address:
  result = await db.execute(select(Address).where(Address.id == address_id))
  address = result.scalar_one_or_none()
  if not address:
    raise HTTPException(status_code=400, detail="Адрес не найден")
  return address


async def _build_ticket_out(ticket: Ticket) -> TicketOut:
  files = []
  for file_item in ticket.files:
    files.append(
      {
        "id": file_item.id,
        "ticket_id": file_item.ticket_id,
        "file_url": await generate_download_url(file_item.file_url, file_item.file_path),
        "file_name": file_item.file_name,
        "mime_type": file_item.mime_type,
        "uploaded_at": file_item.uploaded_at,
      }
    )

  return TicketOut(
    id=ticket.id,
    title=ticket.title,
    description=ticket.description,
    address_id=ticket.address_id,
    status=ticket.status.code,
    user_id=ticket.user_id,
    opened_at=ticket.opened_at,
    closed_at=ticket.closed_at,
    is_closed=ticket.is_closed,
    files=files,
  )


def _build_ticket_list_item(ticket: Ticket) -> TicketListItem:
  return TicketListItem(
    id=ticket.id,
    title=ticket.title,
    address_id=ticket.address_id,
    status=ticket.status.code,
    opened_at=ticket.opened_at,
    is_closed=ticket.is_closed,
  )


async def create_ticket_service(
  db: AsyncSession,
  current_user: User,
  title: str,
  address_id: int,
  description: str | None = None,
  files: list[UploadFile] | None = None,
) -> TicketOut:
  await _ensure_address_exists(db, address_id)
  created_status = await _get_status_by_code(db, CREATED_STATUS_CODE)

  ticket = Ticket(
    title=title,
    description=description,
    address_id=address_id,
    status_id=created_status.id,
    user_id=current_user.id,
  )
  db.add(ticket)
  await db.flush()

  chat = Chat(ticket_id=ticket.id)
  db.add(chat)
  await db.flush()

  db.add(
    ChatParticipant(
      chat_id=chat.id,
      user_id=current_user.id,
      role_in_chat="creator",
    )
  )

  for upload_file in files or []:
    object_key, _ = await upload_file_to_storage(upload_file, "tickets", ticket.id)
    db.add(
      TicketFile(
        ticket_id=ticket.id,
        original_name=upload_file.filename or "file",
        file_path=object_key,
        file_url=object_key,
        file_name=upload_file.filename or "file",
        mime_type=upload_file.content_type,
      )
    )

  await write_audit_log(
    action_type="TICKET_CREATE",
    user=current_user,
    entity_type="Ticket",
    entity_id=str(ticket.id),
    details={"address_id": address_id, "title": title},
    db=db,
  )

  await db.commit()
  ticket = await _get_ticket_by_id(db, ticket.id)
  return await _build_ticket_out(ticket)


async def get_ticket_service(
  db: AsyncSession,
  ticket_id: int,
  current_user: User,
) -> TicketOut:
  ticket = await _get_ticket_by_id(db, ticket_id)
  if not _can_access_ticket(current_user, ticket):
    raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")
  return await _build_ticket_out(ticket)


async def get_tickets_service(db: AsyncSession, current_user: User) -> list[TicketListItem]:
  query = select(Ticket).where(Ticket.user_id == current_user.id).order_by(Ticket.opened_at.desc())
  result = await db.execute(query)
  tickets = result.scalars().all()
  return [_build_ticket_list_item(ticket) for ticket in tickets]


async def get_all_tickets_admin_service(db: AsyncSession, current_user: User) -> list[TicketListItem]:
  _ensure_ticket_read_all(current_user)

  result = await db.execute(select(Ticket).order_by(Ticket.opened_at.desc()))
  tickets = result.scalars().all()
  return [_build_ticket_list_item(ticket) for ticket in tickets]


async def get_ticket_admin_service(db: AsyncSession, ticket_id: int, current_user: User) -> TicketOut:
  _ensure_ticket_read_all(current_user)

  ticket = await _get_ticket_by_id(db, ticket_id)
  return await _build_ticket_out(ticket)


async def get_ticket_statuses_service(db: AsyncSession) -> list[TicketStatusOut]:
  result = await db.execute(select(TicketStatus).order_by(TicketStatus.id))
  return [
    TicketStatusOut(id=status_item.id, code=status_item.code, name=status_item.name)
    for status_item in result.scalars().all()
  ]


async def update_ticket_status_service(
  db: AsyncSession,
  ticket_id: int,
  status_code: str,
  current_user: User,
) -> TicketOut:
  if not has_permission(current_user, TICKETS_UPDATE_STATUS):
    raise HTTPException(status_code=403, detail="Изменять статус заявки может только сотрудник с соответствующим правом")

  status_code = status_code.lower()
  ticket = await _get_ticket_by_id(db, ticket_id)
  ticket_status = await _get_status_by_code(db, status_code)

  ticket.status_id = ticket_status.id
  ticket.is_closed = status_code in FINAL_STATUS_CODES
  if ticket.is_closed and ticket.closed_at is None:
    ticket.closed_at = datetime.utcnow()
  if not ticket.is_closed:
    ticket.closed_at = None

  await write_audit_log(
    action_type="TICKET_STATUS_UPDATE",
    user=current_user,
    entity_type="Ticket",
    entity_id=str(ticket.id),
    details={"status_code": status_code},
    db=db,
  )

  await db.commit()
  ticket = await _get_ticket_by_id(db, ticket.id)
  return await _build_ticket_out(ticket)


async def close_own_ticket_service(db: AsyncSession, ticket_id: int, current_user: User) -> TicketOut:
  ticket = await _get_ticket_by_id(db, ticket_id)
  if ticket.user_id != current_user.id and not _is_staff(current_user):
    raise HTTPException(status_code=403, detail="Закрыть можно только свою заявку")

  closed_status = await _get_status_by_code(db, CLOSED_STATUS_CODE)
  ticket.status_id = closed_status.id
  ticket.is_closed = True
  ticket.closed_at = datetime.utcnow()
  await write_audit_log(
    action_type="TICKET_CLOSE",
    user=current_user,
    entity_type="Ticket",
    entity_id=str(ticket.id),
    details={"status_code": CLOSED_STATUS_CODE},
    db=db,
  )
  await db.commit()

  ticket = await _get_ticket_by_id(db, ticket.id)
  return await _build_ticket_out(ticket)
