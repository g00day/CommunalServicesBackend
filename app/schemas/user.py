from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    surname: str
    father_name: str | None
    full_name: str
    role: str
    is_activated: bool
    uprava_id: int | None
    position: str | None

    class Config:
        from_attributes = True
