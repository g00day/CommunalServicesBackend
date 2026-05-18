from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AdminCreateUserRequest,
    ChangeEmailRequest,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TelegramLinkCodeOut,
    TelegramLinkConfirmOut,
    TelegramLinkConfirmRequest,
    TokenPair,
    UpdateProfileRequest,
)
from app.schemas.user import UserOut
from app.services.audit import write_audit_log
from app.services.auth import (
    authenticate,
    change_password,
    confirm_email,
    confirm_email_change,
    confirm_password_reset,
    confirm_telegram_link_code,
    create_telegram_link_code,
    create_user_by_admin,
    get_current_user_profile,
    issue_tokens,
    refresh_tokens,
    register_user,
    request_email_change,
    request_password_reset,
    update_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(request: Request, db: AsyncSession = Depends(get_db)):
    """Регистрация пользователя."""
    content_type = request.headers.get("content-type", "")
    avatar: UploadFile | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        avatar_candidate = form.get("avatar")
        if avatar_candidate is not None and hasattr(avatar_candidate, "filename"):
            avatar = avatar_candidate

        try:
            payload = RegisterRequest.model_validate(
                {
                    "email": form.get("email"),
                    "password": form.get("password"),
                    "name": form.get("name"),
                    "surname": form.get("surname"),
                    "father_name": form.get("father_name"),
                }
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
    else:
        try:
            payload = RegisterRequest.model_validate(await request.json())
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

    await register_user(
        db,
        payload.email,
        payload.password,
        payload.name,
        payload.surname,
        payload.father_name,
        avatar,
    )
    return {"detail": "Регистрация успешна. Проверьте почту для подтверждения email."}


@router.get("/confirm-email", response_class=HTMLResponse)
async def confirm_email_route(token: str, db: AsyncSession = Depends(get_db)):
    user = await confirm_email(db, token)
    return HTMLResponse(content=_success_page(user.full_name))


@router.post("/request-password-reset", response_model=dict)
async def request_password_reset_route(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    await request_password_reset(db, payload.email)
    return {"detail": "Если аккаунт с таким email существует, письмо для сброса пароля отправлено."}


@router.post("/reset-password/confirm", response_model=dict)
async def reset_password_confirm_route(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    await confirm_password_reset(db, payload.token, payload.new_password)
    return {"detail": "Пароль успешно изменен"}


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
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
    return await refresh_tokens(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    await write_audit_log(
        action_type="USER_LOGOUT",
        user=current_user,
        entity_type="AuthSession",
        entity_id=str(current_user.id),
    )
    return


@router.get("/me", response_model=UserOut)
async def me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_current_user_profile(db, current_user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content_type = request.headers.get("content-type", "")
    avatar: UploadFile | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        avatar_candidate = form.get("avatar")
        if avatar_candidate is not None and hasattr(avatar_candidate, "filename"):
            avatar = avatar_candidate

        try:
            payload = UpdateProfileRequest.model_validate(
                {
                    "name": form.get("name"),
                    "surname": form.get("surname"),
                    "father_name": form.get("father_name"),
                    "position": form.get("position"),
                }
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
    else:
        try:
            payload = UpdateProfileRequest.model_validate(await request.json())
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

    await update_profile(
        db=db,
        current_user=current_user,
        name=payload.name,
        surname=payload.surname,
        father_name=payload.father_name,
        position=payload.position,
        avatar=avatar,
    )
    return await get_current_user_profile(db, current_user)


@router.post("/change-password", response_model=dict)
async def change_password_route(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await change_password(db, current_user, payload.current_password, payload.new_password)
    return {"detail": "Пароль успешно изменен"}


@router.post("/change-email/request", response_model=dict)
async def change_email_request_route(
    payload: ChangeEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await request_email_change(db, current_user, payload.new_email)
    return {"detail": "Письмо для подтверждения смены email отправлено на текущую почту"}


@router.get("/confirm-email-change", response_class=HTMLResponse)
async def confirm_email_change_route(token: str, db: AsyncSession = Depends(get_db)):
    user = await confirm_email_change(db, token)
    return HTMLResponse(content=_email_change_success_page(user.full_name, user.email))


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
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
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


def _email_change_success_page(full_name: str, new_email: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Email изменён</title>
    <style>
        body {{ font-family:Arial,sans-serif; display:flex; justify-content:center;
                align-items:center; min-height:100vh; margin:0; background:#f0f9ff; }}
        .card {{ background:white; border-radius:12px; padding:40px 48px;
                 box-shadow:0 4px 24px rgba(0,0,0,.08); text-align:center; max-width:460px; }}
        h1 {{ color:#16a34a; margin:0 0 8px; font-size:1.5rem; }}
        p {{ color:#6b7280; margin:0; line-height:1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size:48px;margin-bottom:16px">OK</div>
        <h1>Email успешно изменён!</h1>
        <p><strong>{full_name}</strong>, теперь для входа используется адрес:<br>
        <strong>{new_email}</strong></p>
    </div>
</body>
</html>"""
