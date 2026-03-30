from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import CHAT_PARTICIPANTS_MANAGE, TICKETS_READ_ALL, has_permission
from app.core.storage import generate_download_url, upload_file_to_storage
from app.models import Chat, ChatParticipant, Message, MessageFile, Ticket, TicketFile, User
from app.schemas import (
    ChatParticipantOut,
    FileCreate,
    MessageFileOut,
    MessageOut,
    TicketFileOut,
    WebhookMessageOut,
)


def _is_staff(user: User) -> bool:
    return has_permission(user, TICKETS_READ_ALL) or has_permission(user, CHAT_PARTICIPANTS_MANAGE)


async def _get_ticket(db: AsyncSession, ticket_id: int) -> Ticket:
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return ticket


def _can_access_ticket(user: User, ticket: Ticket) -> bool:
    return has_permission(user, TICKETS_READ_ALL) or ticket.user_id == user.id


async def _get_chat_by_ticket(db: AsyncSession, ticket_id: int) -> Chat:
    result = await db.execute(select(Chat).where(Chat.ticket_id == ticket_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат по заявке не найден")
    return chat


async def _get_message(db: AsyncSession, message_id: int) -> Message:
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    return message


async def _is_chat_participant(db: AsyncSession, chat_id: int, user_id: int) -> bool:
    result = await db.execute(
        select(ChatParticipant).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _can_access_chat(db: AsyncSession, user: User, ticket: Ticket, chat: Chat) -> bool:
    if _can_access_ticket(user, ticket):
        return True
    return await _is_chat_participant(db, chat.id, user.id)


async def _get_ticket_and_chat(db: AsyncSession, ticket_id: int) -> tuple[Ticket, Chat]:
    ticket = await _get_ticket(db, ticket_id)
    chat = await _get_chat_by_ticket(db, ticket_id)
    return ticket, chat


async def _get_message_for_ticket(db: AsyncSession, ticket_id: int, message_id: int) -> Message:
    message = await _get_message(db, message_id)
    if message.chat.ticket_id != ticket_id:
        raise HTTPException(status_code=404, detail="Сообщение не относится к этой заявке")
    return message


async def _ensure_participant(
    db: AsyncSession,
    chat_id: int,
    user: User,
    role_in_chat: str | None = None,
) -> None:
    result = await db.execute(
        select(ChatParticipant).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user.id,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is not None:
        return

    db.add(ChatParticipant(chat_id=chat_id, user_id=user.id, role_in_chat=role_in_chat))
    await db.flush()


def _build_message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        chat_id=message.chat_id,
        sender_user_id=message.sender_user_id,
        text=message.text,
        sent_at=message.sent_at,
        files=[
            MessageFileOut(
                id=file_item.id,
                message_id=file_item.message_id,
                file_url=file_item.file_url,
                file_name=file_item.file_name,
                mime_type=file_item.mime_type,
                uploaded_at=file_item.uploaded_at,
            )
            for file_item in message.files
        ],
    )


async def _build_message_out_with_download_urls(message: Message) -> MessageOut:
    files = []
    for file_item in message.files:
        files.append(
            MessageFileOut(
                id=file_item.id,
                message_id=file_item.message_id,
                file_url=await generate_download_url(file_item.file_url, file_item.file_path),
                file_name=file_item.file_name,
                mime_type=file_item.mime_type,
                uploaded_at=file_item.uploaded_at,
            )
        )

    return MessageOut(
        id=message.id,
        chat_id=message.chat_id,
        sender_user_id=message.sender_user_id,
        text=message.text,
        sent_at=message.sent_at,
        files=files,
    )


async def get_ticket_messages_service(db: AsyncSession, ticket_id: int, current_user: User) -> list[MessageOut]:
    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к чату этой заявки")

    result = await db.execute(select(Message).where(Message.chat_id == chat.id).order_by(Message.sent_at))
    return [await _build_message_out_with_download_urls(message) for message in result.scalars().all()]


async def create_message_service(
    db: AsyncSession,
    ticket_id: int,
    text: str | None,
    current_user: User,
    files: list[UploadFile] | None = None,
) -> MessageOut:
    if text is None or not text.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к чату этой заявки")

    await _ensure_participant(db, chat.id, current_user, "participant")

    message = Message(chat_id=chat.id, sender_user_id=current_user.id, text=text.strip())
    db.add(message)

    await db.flush()

    for upload_file in files or []:
        object_key, _ = await upload_file_to_storage(upload_file, "messages", message.id)
        db.add(
            MessageFile(
                message_id=message.id,
                original_name=upload_file.filename or "file",
                file_path=object_key,
                file_url=object_key,
                file_name=upload_file.filename or "file",
                mime_type=upload_file.content_type,
            )
        )

    await db.commit()
    await db.refresh(message)

    message = await _get_message(db, message.id)
    return await _build_message_out_with_download_urls(message)


async def get_chat_participants_service(
    db: AsyncSession,
    ticket_id: int,
    current_user: User,
) -> list[ChatParticipantOut]:
    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к участникам чата")

    result = await db.execute(
        select(ChatParticipant).where(ChatParticipant.chat_id == chat.id).order_by(ChatParticipant.joined_at)
    )
    return [
        ChatParticipantOut(
            user_id=item.user_id,
            role_in_chat=item.role_in_chat,
            joined_at=item.joined_at,
        )
        for item in result.scalars().all()
    ]


async def add_chat_participant_service(
    db: AsyncSession,
    ticket_id: int,
    user_id: int,
    role_in_chat: str | None,
    current_user: User,
) -> ChatParticipantOut:
    if not has_permission(current_user, CHAT_PARTICIPANTS_MANAGE):
        raise HTTPException(status_code=403, detail="Добавлять участников чата может только сотрудник с соответствующим правом")

    _, chat = await _get_ticket_and_chat(db, ticket_id)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await _ensure_participant(db, chat.id, user, role_in_chat)
    await db.commit()

    result = await db.execute(
        select(ChatParticipant).where(
            ChatParticipant.chat_id == chat.id,
            ChatParticipant.user_id == user_id,
        )
    )
    participant = result.scalar_one()
    return ChatParticipantOut(
        user_id=participant.user_id,
        role_in_chat=participant.role_in_chat,
        joined_at=participant.joined_at,
    )


async def get_ticket_files_service(db: AsyncSession, ticket_id: int, current_user: User) -> list[TicketFileOut]:
    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к файлам заявки")

    result = await db.execute(select(TicketFile).where(TicketFile.ticket_id == ticket_id).order_by(TicketFile.uploaded_at))
    items = []
    for item in result.scalars().all():
        items.append(
            TicketFileOut(
                id=item.id,
                ticket_id=item.ticket_id,
                file_url=await generate_download_url(item.file_url, item.file_path),
                file_name=item.file_name,
                mime_type=item.mime_type,
                uploaded_at=item.uploaded_at,
            )
        )
    return items


async def add_ticket_file_service(
    db: AsyncSession,
    ticket_id: int,
    file_url: str,
    file_name: str,
    mime_type: str | None,
    current_user: User,
) -> TicketFileOut:
    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к файлам заявки")

    ticket_file = TicketFile(
        ticket_id=ticket_id,
        original_name=file_name,
        file_path=file_url,
        file_url=file_url,
        file_name=file_name,
        mime_type=mime_type,
    )
    db.add(ticket_file)
    await db.commit()
    await db.refresh(ticket_file)
    return TicketFileOut(
        id=ticket_file.id,
        ticket_id=ticket_file.ticket_id,
        file_url=await generate_download_url(ticket_file.file_url, ticket_file.file_path),
        file_name=ticket_file.file_name,
        mime_type=ticket_file.mime_type,
        uploaded_at=ticket_file.uploaded_at,
    )


async def get_message_files_service(
    db: AsyncSession,
    ticket_id: int,
    message_id: int,
    current_user: User,
) -> list[MessageFileOut]:
    await _get_message_for_ticket(db, ticket_id, message_id)
    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к файлам сообщения")

    result = await db.execute(select(MessageFile).where(MessageFile.message_id == message_id).order_by(MessageFile.uploaded_at))
    items = []
    for item in result.scalars().all():
        items.append(
            MessageFileOut(
                id=item.id,
                message_id=item.message_id,
                file_url=await generate_download_url(item.file_url, item.file_path),
                file_name=item.file_name,
                mime_type=item.mime_type,
                uploaded_at=item.uploaded_at,
            )
        )
    return items


async def add_message_file_service(
    db: AsyncSession,
    ticket_id: int,
    message_id: int,
    file_url: str,
    file_name: str,
    mime_type: str | None,
    current_user: User,
) -> MessageFileOut:
    await _get_message_for_ticket(db, ticket_id, message_id)
    ticket, chat = await _get_ticket_and_chat(db, ticket_id)
    if not await _can_access_chat(db, current_user, ticket, chat):
        raise HTTPException(status_code=403, detail="Нет доступа к файлам сообщения")

    message_file = MessageFile(
        message_id=message_id,
        original_name=file_name,
        file_path=file_url,
        file_url=file_url,
        file_name=file_name,
        mime_type=mime_type,
    )
    db.add(message_file)
    await db.commit()
    await db.refresh(message_file)
    return MessageFileOut(
        id=message_file.id,
        message_id=message_file.message_id,
        file_url=await generate_download_url(message_file.file_url, message_file.file_path),
        file_name=message_file.file_name,
        mime_type=message_file.mime_type,
        uploaded_at=message_file.uploaded_at,
    )


async def upload_message_file_service(
    db: AsyncSession,
    ticket_id: int,
    message_id: int,
    upload_file: UploadFile,
    current_user: User,
) -> MessageFileOut:
    await _get_message_for_ticket(db, ticket_id, message_id)
    object_key, _ = await upload_file_to_storage(upload_file, "messages", message_id)
    return await add_message_file_service(
        db=db,
        ticket_id=ticket_id,
        message_id=message_id,
        file_url=object_key,
        file_name=upload_file.filename or "file",
        mime_type=upload_file.content_type,
        current_user=current_user,
    )


async def create_message_from_webhook_service(
    db: AsyncSession,
    ticket_id: int,
    text: str | None,
    files: list[FileCreate],
    sender_user_id: int | None = None,
    sender_tg_chat_id: int | None = None,
    role_in_chat: str | None = "participant",
) -> WebhookMessageOut:
    if sender_user_id is None and sender_tg_chat_id is None:
        raise HTTPException(status_code=400, detail="Нужно передать sender_user_id или sender_tg_chat_id")
    if text is None or not text.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    ticket, chat = await _get_ticket_and_chat(db, ticket_id)

    user_query = select(User)
    if sender_user_id is not None:
        user_query = user_query.where(User.id == sender_user_id)
    else:
        user_query = user_query.where(User.tg_chat_id == sender_tg_chat_id)

    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Отправитель вебхука не найден")

    if not await _can_access_chat(db, user, ticket, chat):
        raise HTTPException(status_code=403, detail="Отправитель не имеет доступа к чату")

    await _ensure_participant(db, chat.id, user, role_in_chat)

    message = Message(chat_id=chat.id, sender_user_id=user.id, text=text.strip())
    db.add(message)
    await db.flush()

    for file_item in files:
        db.add(
            MessageFile(
                message_id=message.id,
                original_name=file_item.file_name,
                file_path=file_item.file_url,
                file_url=file_item.file_url,
                file_name=file_item.file_name,
                mime_type=file_item.mime_type,
            )
        )

    await db.commit()
    message = await _get_message(db, message.id)
    return WebhookMessageOut(status="принято", message=await _build_message_out_with_download_urls(message))
