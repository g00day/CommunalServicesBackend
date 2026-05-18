from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.file import MessageFileOut


class TelegramBotUserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_admin: bool
    can_manage_tickets: bool
    tg_chat_id: int


class TelegramBotTicketListItemOut(BaseModel):
    id: int
    title: str
    status: str
    opened_at: datetime
    is_closed: bool
    address_label: str | None = None


class TelegramBotTicketDetailOut(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    is_closed: bool
    creator_name: str
    address_label: str | None = None


class TelegramBotMessageOut(BaseModel):
    id: int
    sender_user_id: int
    sender_name: str
    text: str | None
    sent_at: datetime
    files: list[MessageFileOut] = Field(default_factory=list)


class TelegramBotCloseTicketRequest(BaseModel):
    tg_chat_id: int


class TelegramBotStatusUpdateRequest(BaseModel):
    tg_chat_id: int
    status_code: str = Field(min_length=3, max_length=30)
