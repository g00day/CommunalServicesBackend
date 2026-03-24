from datetime import datetime, timedelta, timezone
import secrets

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.mail import send_confirmation_email, send_password_reset_email
from app.core.permissions import USERS_CREATE, require_permission
from app.core.security import (
    create_access_token,
    create_email_confirm_token,
    create_refresh_token,
    create_reset_password_token,
    decode_email_confirm_token,
    decode_password_reset_token,
    hash_password,
    verify_password
)
from app.models import Role, TelegramLinkCode, User

DEFAULT_ROLE_ID = 1


async def _ensure_role_exists(db: AsyncSession, role_id: int) -> Role:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    return role


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
    surname: str,
    father_name: str | None = None,
) -> User:
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


async def create_user_by_admin(
    db: AsyncSession,
    current_user: User,
    email: str,
    password: str,
    name: str,
    surname: str,
    role_id: int,
    father_name: str | None = None,
    uprava_id: int | None = None,
    position: str | None = None,
    tg_chat_id: int | None = None,
) -> User:
    require_permission(
        current_user,
        USERS_CREATE,
        detail="Создание пользователей доступно только сотруднику с соответствующим правом",
    )
    await _ensure_role_exists(db, role_id)

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")

    user = User(
        email=email,
        name=name,
        surname=surname,
        father_name=father_name,
        hash_pass=hash_password(password),
        role_id=role_id,
        is_activated=True,
        uprava_id=uprava_id,
        position=position,
        tg_chat_id=tg_chat_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def request_password_reset(db: AsyncSession, email: str) -> None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return

    token = create_reset_password_token(email)
    await send_password_reset_email(email, token)


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
        raise HTTPException(status_code=400, detail="Email уже подтвержден")

    user.is_activated = True
    await db.commit()
    await db.refresh(user)
    return user


async def confirm_password_reset(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> User:
    try:
        email = decode_password_reset_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Недействительный токен")

    user.hash_pass = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hash_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    if not user.is_activated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email не подтвержден. Проверьте почту.",
        )

    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict:
    exc = HTTPException(status_code=401, detail="Недействительный refresh-токен")
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise exc
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_activated:
        raise exc

    return issue_tokens(user)


async def _cleanup_expired_telegram_link_codes(db: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        delete(TelegramLinkCode).where(
            TelegramLinkCode.expires_at < now,
        )
    )


async def create_telegram_link_code(db: AsyncSession, current_user: User) -> TelegramLinkCode:
    await _cleanup_expired_telegram_link_codes(db)
    await db.execute(delete(TelegramLinkCode).where(TelegramLinkCode.user_id == current_user.id))

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.TELEGRAM_LINK_CODE_MINUTES)

    code = ""
    for _ in range(10):
        candidate = f"{secrets.randbelow(1_000_000):06d}"
        existing = await db.execute(
            select(TelegramLinkCode).where(
                TelegramLinkCode.code == candidate,
                TelegramLinkCode.consumed_at.is_(None),
                TelegramLinkCode.expires_at >= datetime.now(timezone.utc),
            )
        )
        if existing.scalar_one_or_none() is None:
            code = candidate
            break

    if not code:
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать код привязки Telegram")

    link_code = TelegramLinkCode(
        user_id=current_user.id,
        code=code,
        expires_at=expires_at,
    )
    db.add(link_code)
    await db.commit()
    await db.refresh(link_code)
    return link_code


async def confirm_telegram_link_code(db: AsyncSession, code: str, tg_chat_id: int) -> User:
    await _cleanup_expired_telegram_link_codes(db)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(TelegramLinkCode).where(
            TelegramLinkCode.code == code,
            TelegramLinkCode.consumed_at.is_(None),
            TelegramLinkCode.expires_at >= now,
        )
    )
    link_code = result.scalar_one_or_none()
    if not link_code:
        raise HTTPException(status_code=404, detail="Код привязки не найден или истек")

    user_result = await db.execute(select(User).where(User.id == link_code.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь для привязки не найден")

    await db.execute(
        update(User)
        .where(User.tg_chat_id == tg_chat_id, User.id != user.id)
        .values(tg_chat_id=None)
    )
    user.tg_chat_id = tg_chat_id
    link_code.consumed_at = now
    await db.commit()
    await db.refresh(user)
    return user


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }
