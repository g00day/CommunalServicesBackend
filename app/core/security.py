from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(str(user_id), "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES))


def create_refresh_token(user_id: int) -> str:
    return _create_token(str(user_id), "refresh", timedelta(days=settings.REFRESH_TOKEN_DAYS))


def create_email_confirm_token(email: str) -> str:
    return _create_token(email, "email_confirm", timedelta(hours=24))


def decode_email_confirm_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "email_confirm":
            raise ValueError("Неверный тип токена")
        return payload["sub"]
    except (JWTError, KeyError):
        raise ValueError("Токен недействителен или истёк")


def create_reset_password_token(email: str) -> str:
    return _create_token(email, "reset_password", timedelta(hours=1))


def decode_password_reset_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "reset_password":
            raise ValueError("Неверный тип токена")
        return payload["sub"]
    except (JWTError, KeyError):
        raise ValueError("Токен недействителен или истёк")


def create_email_change_token(user_id: int, current_email: str, new_email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "email_change",
        "current_email": current_email,
        "new_email": new_email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_email_change_token(token: str) -> tuple[int, str, str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "email_change":
            raise ValueError("Неверный тип токена")
        return int(payload["sub"]), payload["current_email"], payload["new_email"]
    except (JWTError, KeyError, ValueError):
        raise ValueError("Токен недействителен или истёк")
