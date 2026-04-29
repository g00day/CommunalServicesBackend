from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings

_conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_SSL_TLS=settings.MAIL_SSL,
    MAIL_STARTTLS=settings.MAIL_TLS,
    USE_CREDENTIALS=True,
)

_mailer = FastMail(_conf)


def _build_app_url(path: str) -> str:
    return f"{settings.APP_BASE_URL}{path}"


async def send_confirmation_email(to_email: str, token: str) -> None:
    confirm_url = _build_app_url(f"/api/auth/confirm-email?token={token}")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
        <h2 style="color:#2563eb;">Подтверждение email</h2>
        <p>Вы зарегистрировались в системе <strong>ЖКХ Диспетчерская</strong>.</p>
        <a href="{confirm_url}"
           style="display:inline-block;padding:12px 24px;background:#2563eb;
                  color:#fff;text-decoration:none;border-radius:6px;margin:16px 0;">
            Подтвердить email
        </a>
        <p style="color:#9ca3af;font-size:12px;">
            Или скопируйте ссылку вручную:<br>
            <a href="{confirm_url}">{confirm_url}</a>
        </p>
    </div>
    """
    message = MessageSchema(
        subject="Подтверждение email — ЖКХ Диспетчерская",
        recipients=[to_email],
        body=html,
        subtype=MessageType.html
    )
    await _mailer.send_message(message)
    
async def send_password_reset_email(to_email: str, token: str) -> None: 
    reset_url = _build_app_url(f"/api/auth/reset-password?token={token}")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
        <h2 style="color:#2563eb;">Сброс пароля</h2>

        <p>Вы запросили сброс пароля в системе <strong>ЖКХ Диспетчерская</strong>.</p>

        <p>Нажмите на кнопку ниже, чтобы задать новый пароль:</p>

        <a href="{reset_url}"
           style="display:inline-block;padding:12px 24px;background:#2563eb;
                  color:#fff;text-decoration:none;border-radius:6px;margin:16px 0;">
            Сбросить пароль
        </a>

        <p style="color:#9ca3af;font-size:12px;">
            Если кнопка не работает, скопируйте ссылку вручную:<br>
            <a href="{reset_url}">{reset_url}</a>
        </p>

        <p style="color:#9ca3af;font-size:12px;">
            Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.
        </p>
    </div>
    """
    
    message = MessageSchema(
        subject="Сброс пароля — ЖКХ Диспетчерская",
        recipients=[to_email],
        body=html,
        subtype=MessageType.html
    )
    await _mailer.send_message(message)
