import asyncio
import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import TICKETS_READ_ALL, has_permission
from app.models import Message, Ticket, User

logger = logging.getLogger(__name__)


def _can_send_notifications() -> bool:
    return bool(settings.TELEGRAM_BOT_SERVICE_URL and settings.TELEGRAM_BOT_INTERNAL_SECRET)


def _post_json(url: str, payload: dict, secret: str, timeout: int) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Bot-Secret": secret,
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        response.read()


async def _dispatch_notification(payload: dict) -> None:
    if not _can_send_notifications():
        return

    url = f"{settings.TELEGRAM_BOT_SERVICE_URL.rstrip('/')}/internal/notify"
    secret = settings.TELEGRAM_BOT_INTERNAL_SECRET or ""
    try:
        await asyncio.to_thread(
            _post_json,
            url,
            payload,
            secret,
            settings.TELEGRAM_BOT_NOTIFY_TIMEOUT_SECONDS,
        )
    except (URLError, OSError, TimeoutError) as exc:
        logger.warning("Telegram bot notification failed: %s", exc)


async def _staff_chat_ids(db: AsyncSession) -> set[int]:
    result = await db.execute(select(User).where(User.tg_chat_id.is_not(None)))
    users = result.scalars().all()
    return {
        user.tg_chat_id
        for user in users
        if user.tg_chat_id is not None and has_permission(user, TICKETS_READ_ALL)
    }


async def notify_ticket_created(db: AsyncSession, ticket: Ticket) -> None:
    recipient_chat_ids = await _staff_chat_ids(db)
    if not recipient_chat_ids:
        return

    await _dispatch_notification(
        {
            "event": "ticket_created",
            "recipient_chat_ids": sorted(recipient_chat_ids),
            "ticket": {
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status.code,
            },
        }
    )


async def notify_ticket_status_changed(db: AsyncSession, ticket: Ticket, actor_user_id: int | None = None) -> None:
    result = await db.execute(select(User).where(User.id == ticket.user_id))
    owner = result.scalar_one_or_none()
    if not owner or owner.tg_chat_id is None:
        return
    if actor_user_id is not None and actor_user_id == owner.id:
        return

    await _dispatch_notification(
        {
            "event": "ticket_status_changed",
            "recipient_chat_ids": [owner.tg_chat_id],
            "ticket": {
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status.code,
            },
        }
    )


async def notify_new_message(db: AsyncSession, ticket: Ticket, message: Message) -> None:
    result = await db.execute(select(User).where(User.id == message.sender_user_id))
    sender = result.scalar_one_or_none()

    recipient_chat_ids: set[int] = set()
    if ticket.creator.tg_chat_id is not None:
        recipient_chat_ids.add(ticket.creator.tg_chat_id)

    if sender and not has_permission(sender, TICKETS_READ_ALL):
        recipient_chat_ids.update(await _staff_chat_ids(db))

    if sender and sender.tg_chat_id is not None:
        recipient_chat_ids.discard(sender.tg_chat_id)

    if not recipient_chat_ids:
        return

    await _dispatch_notification(
        {
            "event": "message_created",
            "recipient_chat_ids": sorted(recipient_chat_ids),
            "ticket": {
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status.code,
            },
            "message": {
                "id": message.id,
                "text": message.text,
                "sender_name": sender.full_name if sender else "Пользователь",
                "has_files": bool(message.files),
            },
        }
    )
