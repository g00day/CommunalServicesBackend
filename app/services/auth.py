from datetime import datetime, timedelta, timezone
import secrets

from fastapi import HTTPException, UploadFile, status
from jose import JWTError, jwt
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.mail import (
    send_confirmation_email,
    send_email_change_confirmation_email,
    send_password_reset_email,
)
from app.core.permissions import ADMIN_ACCESS, REPORTS_READ, USERS_CREATE, has_permission, require_permission
from app.core.security import (
    create_access_token,
    create_email_change_token,
    create_email_confirm_token,
    create_refresh_token,
    create_reset_password_token,
    decode_email_change_token,
    decode_email_confirm_token,
    decode_password_reset_token,
    hash_password,
    verify_password
)
from app.core.storage import generate_download_url, upload_file_to_storage
from app.models import Role, TelegramLinkCode, Ticket, TicketStatus, User

DEFAULT_ROLE_ID = 1  # может в .env вынести? 


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
    avatar: UploadFile | None = None,
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
    await db.flush()

    if avatar is not None:
        object_key, file_url = await upload_file_to_storage(avatar, "avatars", user.id)
        user.avatar_path = object_key
        user.avatar_url = file_url

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


async def change_password(
    db: AsyncSession,
    current_user: User,
    current_password: str,
    new_password: str,
) -> User:
    if not verify_password(current_password, current_user.hash_pass):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текущий пароль указан неверно",
        )
    if verify_password(new_password, current_user.hash_pass):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль должен отличаться от текущего",
        )

    current_user.hash_pass = hash_password(new_password)
    await db.commit()
    await db.refresh(current_user)
    return current_user


async def update_profile(
    db: AsyncSession,
    current_user: User,
    name: str | None = None,
    surname: str | None = None,
    father_name: str | None = None,
    position: str | None = None,
    avatar: UploadFile | None = None,
) -> User:
    if name is not None:
        current_user.name = name
    if surname is not None:
        current_user.surname = surname
    if father_name is not None:
        current_user.father_name = father_name or None
    if position is not None:
        current_user.position = position or None

    if avatar is not None:
        object_key, file_url = await upload_file_to_storage(avatar, "avatars", current_user.id)
        current_user.avatar_path = object_key
        current_user.avatar_url = file_url

    await db.commit()
    await db.refresh(current_user)
    return current_user


async def request_email_change(
    db: AsyncSession,
    current_user: User,
    new_email: str,
) -> None:
    normalized_email = new_email.strip().lower()
    if normalized_email == current_user.email.lower():
        raise HTTPException(status_code=400, detail="Укажите новый email, отличный от текущего")

    existing = await db.execute(select(User).where(User.email == normalized_email))
    existing_user = existing.scalar_one_or_none()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=409, detail="Email уже используется")

    token = create_email_change_token(current_user.id, current_user.email, normalized_email)
    await send_email_change_confirmation_email(current_user.email, normalized_email, token)


async def confirm_email_change(db: AsyncSession, token: str) -> User:
    try:
        user_id, current_email, new_email = decode_email_change_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.email.lower() != current_email.lower():
        raise HTTPException(status_code=400, detail="Текущий email пользователя уже изменён")

    existing = await db.execute(select(User).where(User.email == new_email))
    existing_user = existing.scalar_one_or_none()
    if existing_user and existing_user.id != user.id:
        raise HTTPException(status_code=409, detail="Email уже используется")

    user.email = new_email
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


async def get_current_user_profile(db: AsyncSession, current_user: User) -> dict:
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions), selectinload(User.uprava))
        .where(User.id == current_user.id)
    )
    current_user = result.scalar_one()

    closed_tickets_query = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.user_id == current_user.id,
            Ticket.is_closed.is_(True),
        )
    )
    in_progress_query = await db.execute(
        select(func.count(Ticket.id))
        .join(TicketStatus, TicketStatus.id == Ticket.status_id)
        .where(
            Ticket.user_id == current_user.id,
            Ticket.is_closed.is_(False),
            TicketStatus.code == "in_progress",
        )
    )

    avatar_url = None
    if current_user.avatar_url or current_user.avatar_path:
        avatar_url = await generate_download_url(
            file_url=current_user.avatar_url,
            file_path=current_user.avatar_path,
        )

    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "surname": current_user.surname,
        "father_name": current_user.father_name,
        "full_name": current_user.full_name,
        "avatar_url": avatar_url,
        "role": current_user.role.name,
        "is_activated": current_user.is_activated,
        "uprava_id": current_user.uprava_id,
        "uprava_name": current_user.uprava.name if current_user.uprava else None,
        "position": current_user.position,
        "tg_chat_id": current_user.tg_chat_id,
        "last_login": current_user.last_login,
        "closed_tickets_count": closed_tickets_query.scalar_one(),
        "in_progress_tickets_count": in_progress_query.scalar_one(),
        "permissions": sorted(current_user.permission_codes),
        "is_admin": has_permission(current_user, ADMIN_ACCESS),
        "can_view_reports": has_permission(current_user, REPORTS_READ),
        "can_use_ai": has_permission(current_user, ADMIN_ACCESS),
    }


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
