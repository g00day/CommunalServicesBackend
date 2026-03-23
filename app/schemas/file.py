from datetime import datetime

from pydantic import BaseModel, Field


class FileCreate(BaseModel):
    file_url: str = Field(min_length=3, max_length=500)
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)


class TicketFileOut(BaseModel):
    id: int
    ticket_id: int
    file_url: str
    file_name: str
    mime_type: str | None
    uploaded_at: datetime


class MessageFileOut(BaseModel):
    id: int
    message_id: int
    file_url: str
    file_name: str
    mime_type: str | None
    uploaded_at: datetime
