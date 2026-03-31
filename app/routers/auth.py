from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AdminCreateUserRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TelegramLinkCodeOut,
    TelegramLinkConfirmOut,
    TelegramLinkConfirmRequest,
    TokenPair,
)
from app.schemas.user import UserOut
from app.services.audit import write_audit_log
from app.services.auth import (
    authenticate,
    confirm_email,
    confirm_password_reset,
    confirm_telegram_link_code,
    create_telegram_link_code,
    create_user_by_admin,
    issue_tokens,
    refresh_tokens,
    register_user,
    request_password_reset,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация. После успешной регистрации на email придет ссылка для активации."""
    await register_user( 
        db,
        payload.email,
        payload.password,
        payload.name,
        payload.surname,
        payload.father_name,
    )
    return {"detail": "Регистрация успешна. Проверьте почту для подтверждения email."}


@router.get("/confirm-email", response_class=HTMLResponse)
async def confirm_email_route(token: str, db: AsyncSession = Depends(get_db)):
    """Ссылка из письма. Активирует аккаунт и показывает HTML-страницу."""
    user = await confirm_email(db, token)
    return HTMLResponse(content=_success_page(user.full_name))


@router.post("/request-password-reset", response_model=dict)
async def request_password_reset_route( payload: PasswordResetRequest, db: AsyncSession = Depends(get_db),
):
    await request_password_reset(db, payload.email)
    return {"detail": "Если аккаунт с таким email существует, письмо для сброса пароля отправлено."}


@router.post("/reset-password/confirm", response_model=dict)
async def reset_password_confirm_route(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db),
):
    await confirm_password_reset(db, payload.token, payload.new_password)
    return {"detail": "Пароль успешно изменен"}


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Вход. Возвращает access + refresh токены. 403 если email не подтвержден."""
    user = await authenticate(db, payload.email, payload.password)
    await write_audit_log(
        action_type="USER_LOGIN",
        user=user,
        entity_type="AuthSession",
        entity_id=str(user.id),
        db=db,
        commit=True,
    )
    return issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Обновление пары токенов по refresh_token."""
    return await refresh_tokens(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    """Stateless logout - клиент удаляет токены у себя."""
    await write_audit_log(
        action_type="USER_LOGOUT",
        user=current_user,
        entity_type="AuthSession",
        entity_id=str(current_user.id),
    )
    return


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Профиль текущего пользователя."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "surname": current_user.surname,
        "father_name": current_user.father_name,
        "full_name": current_user.full_name,
        "role": current_user.role.name,
        "is_activated": current_user.is_activated,
        "uprava_id": current_user.uprava_id,
        "position": current_user.position,
    }


@router.post("/admin/create-user", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    payload: AdminCreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await create_user_by_admin(
        db=db,
        current_user=current_user,
        email=payload.email,
        password=payload.password,
        name=payload.name,
        surname=payload.surname,
        father_name=payload.father_name,
        role_id=payload.role_id,
        uprava_id=payload.uprava_id,
        position=payload.position,
        tg_chat_id=payload.tg_chat_id,
    )
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "surname": user.surname,
        "father_name": user.father_name,
        "full_name": user.full_name,
        "role": user.role.name,
        "is_activated": user.is_activated,
        "uprava_id": user.uprava_id,
        "position": user.position,
    }


@router.post("/telegram/link-code", response_model=TelegramLinkCodeOut)
async def generate_telegram_link_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    link_code = await create_telegram_link_code(db, current_user)
    return {
        "code": link_code.code,
        "expires_at": link_code.expires_at.isoformat(),
    }


@router.post("/telegram/link-confirm", response_model=TelegramLinkConfirmOut)
async def telegram_link_confirm(
    payload: TelegramLinkConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await confirm_telegram_link_code(db, payload.code, payload.tg_chat_id)
    return {
        "detail": "Чат Telegram успешно привязан",
        "user_id": user.id,
        "tg_chat_id": user.tg_chat_id,
    }


@router.post("/dev/activate", include_in_schema=settings.DEBUG, tags=["dev"])
async def dev_activate(email: str, db: AsyncSession = Depends(get_db)):
    """Активирует аккаунт вручную. Виден только при DEBUG=True."""
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException

        raise HTTPException(404, "Пользователь не найден")
    user.is_activated = True
    await db.commit()
    return {"detail": f"{email} активирован"}


def _success_page(full_name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Email подтвержден</title>
    <style>
        body {{ font-family:Arial,sans-serif; display:flex; justify-content:center;
                align-items:center; min-height:100vh; margin:0; background:#f0f9ff; }}
        .card {{ background:white; border-radius:12px; padding:40px 48px;
                 box-shadow:0 4px 24px rgba(0,0,0,.08); text-align:center; max-width:420px; }}
        h1 {{ color:#16a34a; margin:0 0 8px; font-size:1.5rem; }}
        p {{ color:#6b7280; margin:0; }}
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size:48px;margin-bottom:16px">OK</div>
        <h1>Email подтвержден!</h1>
        <p>Добро пожаловать, <strong>{full_name}</strong>.<br>
        Аккаунт активирован. Можете войти в систему.</p>
    </div>
</body>
</html>"""
