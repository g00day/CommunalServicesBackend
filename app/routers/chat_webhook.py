from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas import WebhookMessageCreate, WebhookMessageOut
from app.services.ticket_chat import create_message_from_webhook_service

router = APIRouter(prefix="/chat", tags=["chat-webhook"])


def _validate_webhook_secret(x_webhook_secret: str | None) -> None:
    expected_secret = settings.CHAT_WEBHOOK_SECRET
    if not expected_secret:
        return
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post("/webhook", response_model=WebhookMessageOut)
async def receive_chat_webhook(
    payload: WebhookMessageCreate,
    x_webhook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_webhook_secret(x_webhook_secret)
    return await create_message_from_webhook_service(
        db=db,
        ticket_id=payload.ticket_id,
        text=payload.text,
        files=payload.files,
        sender_user_id=payload.sender_user_id,
        sender_tg_chat_id=payload.sender_tg_chat_id,
        role_in_chat=payload.role_in_chat,
    )
