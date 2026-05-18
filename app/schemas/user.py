from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    surname: str
    father_name: str | None
    full_name: str
    avatar_url: str | None = None
    role: str
    is_activated: bool
    uprava_id: int | None
    uprava_name: str | None = None
    position: str | None
    tg_chat_id: int | None = None
    last_login: datetime | None = None
    closed_tickets_count: int = 0
    in_progress_tickets_count: int = 0
    permissions: list[str] = []
    is_admin: bool = False
    can_view_reports: bool = False
    can_use_ai: bool = False

    model_config = ConfigDict(from_attributes=True)
