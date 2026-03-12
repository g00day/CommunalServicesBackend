from datetime import datetime, timezone

from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.user import User
from app.models.role import Role
from app.core.config import settings
from app.core.security import hash_password,verify_password,create_access_token, create_refresh_token, create_email_confirm_token, decode_email_confirm_token, create_reset_password_token, decode_password_reset_token
from app.core.mail import send_confirmation_email, send_password_reset_email

DEFAULT_ROLE_ID = 1


async def register_user(db: AsyncSession, email: str, password: str, name: str, surname: str, father_name: str | None = None,) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")

    user = User(
        email=email,
        name=name,
        surname=surname,
        father_name=father_name,
        hash_pass=hash_password(password),
        role_id=DEFAULT_ROLE_ID,
        is_activated=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_email_confirm_token(email)
    await send_confirmation_email(email, token)

    return user

async def reset_password(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Email не найден")
    
    token = create_reset_password_token(email)
    await send_password_reset_email(email, token)
    
    return True
    
async def confirm_email(db: AsyncSession, token: str) -> User:
    try:
        email = decode_email_confirm_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.is_activated:
        raise HTTPException(status_code=400, detail="Email уже подтверждён")

    user.is_activated = True
    await db.commit()
    await db.refresh(user)
    return user

async def reset_password_confirm(db: AsyncSession, token: str, new_password: str):
    try:
        email = decode_password_reset_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"{email} Пользователь не найден")

    user.hash_pass = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    return user
    

async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hash_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    if not user.is_activated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email не подтверждён. Проверьте почту.",
        )

    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict:
    exc = HTTPException(status_code=401, detail="Недействительный refresh-токен")
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise exc
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_activated:
        raise exc

    return issue_tokens(user)


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }
