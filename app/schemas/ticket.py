from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.file import TicketFileOut


class TicketCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=1000)
    address_id: int


class TicketStatusUpdate(BaseModel):
    status_code: str = Field(min_length=3, max_length=30)


class TicketOut(BaseModel):
    id: int
    title: str
    description: str | None
    address_id: int
    status: str
    user_id: int
    creator_name: str | None = None
    opened_at: datetime
    closed_at: datetime | None
    is_closed: bool
    files: list[TicketFileOut] = []


class TicketListItem(BaseModel):
    id: int
    title: str
    address_id: int
    status: str
    opened_at: datetime
    is_closed: bool


class TicketStatusOut(BaseModel):
    id: int
    code: str
    name: str
