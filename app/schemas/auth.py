from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=100)
    surname: str = Field(min_length=2, max_length=100)
    father_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=100)
    surname: str = Field(min_length=2, max_length=100)
    father_name: str | None = Field(default=None, max_length=100)
    role_id: int
    uprava_id: int | None = None
    position: str | None = Field(default=None, max_length=120)
    tg_chat_id: int | None = None


class TelegramLinkCodeOut(BaseModel):
    code: str
    expires_at: str


class TelegramLinkConfirmRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    tg_chat_id: int


class TelegramLinkConfirmOut(BaseModel):
    detail: str
    user_id: int
    tg_chat_id: int
