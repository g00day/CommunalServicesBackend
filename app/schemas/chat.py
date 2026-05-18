from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.file import MessageFileOut
from app.schemas.file import FileCreate


class ChatParticipantCreate(BaseModel):
    user_id: int
    role_in_chat: str | None = Field(default=None, max_length=50)


class ChatParticipantOut(BaseModel):
    user_id: int
    role_in_chat: str | None
    joined_at: datetime


class MessageCreate(BaseModel):
    text: str | None = Field(default=None, max_length=5000)


class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender_user_id: int
    sender_name: str
    text: str | None
    sent_at: datetime
    files: list[MessageFileOut] = Field(default_factory=list)


class WebhookMessageCreate(BaseModel):
    ticket_id: int
    text: str | None = Field(default=None, max_length=5000)
    sender_user_id: int | None = None
    sender_tg_chat_id: int | None = None
    role_in_chat: str | None = Field(default="participant", max_length=50)
    files: list[FileCreate] = Field(default_factory=list)


class WebhookMessageOut(BaseModel):
    status: str
    message: MessageOut
