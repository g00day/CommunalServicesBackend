from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, TokenPair, PasswordResetConfirm
from app.schemas.user import UserOut
from app.services.auth import register_user, authenticate, refresh_tokens, issue_tokens, confirm_email, reset_password, reset_password_confirm
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация. После успешной регистрации на email придёт ссылка для активации."""
    await register_user(db, payload.email, payload.password, payload.name, payload.surname, payload.father_name)
    return {"detail": "Регистрация успешна. Проверьте почту для подтверждения email."}

@router.get("/confirm-email", response_class=HTMLResponse)
async def confirm_email_route(token: str, db: AsyncSession = Depends(get_db)):
    """Ссылка из письма. Активирует аккаунт и показывает HTML-страницу."""
    user = await confirm_email(db, token)
    return HTMLResponse(content=_success_page(user.full_name))

@router.post("/request-password-reset")
async def request_password_reset(email: str, db: AsyncSession = Depends(get_db)):
    await reset_password(db, email)
    return {"detail": "Проверьте почту для сброса пароля."}

@router.put("/reset-password", response_class=HTMLResponse)
async def reset_password_route(token: str, payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    user = await reset_password_confirm(db, token, payload.new_password)
    return {"detail": "Пароль успешно изменён"}


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Вход. Возвращает access + refresh токены. 403 если email не подтверждён."""
    user = await authenticate(db, payload.email, payload.password)
    return issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Обновление пары токенов по refresh_token."""
    return await refresh_tokens(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(_: User = Depends(get_current_user)):
    """Stateless logout — клиент удаляет токены у себя."""
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

# активация без email (в будущем уберем)
@router.post("/dev/activate", include_in_schema=settings.DEBUG, tags=["dev"])
async def dev_activate(email: str, db: AsyncSession = Depends(get_db)):
    """Активирует аккаунт вручную. Виден только при DEBUG=True."""
    from sqlalchemy import select
    from app.models.user import User
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
    <title>Email подтверждён</title>
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
        <div style="font-size:48px;margin-bottom:16px">✅</div>
        <h1>Email подтверждён!</h1>
        <p>Добро пожаловать, <strong>{full_name}</strong>.<br>
        Аккаунт активирован. Можете войти в систему.</p>
    </div>
</body>
</html>"""
