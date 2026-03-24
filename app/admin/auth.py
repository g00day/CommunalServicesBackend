from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.permissions import ADMIN_ACCESS, has_permission
from app.core.database import AsyncSessionLocal
from app.models import Role, User
from app.services.auth import authenticate


def _serialize_permissions(user: User) -> list[str]:
    return sorted(user.permission_codes)


class AdminAuth(AuthenticationBackend):
    def __init__(self, secret_key: str):
        super().__init__(secret_key=secret_key)

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username")
        password = form.get("password")

        if not email or not password:
            return False

        async with AsyncSessionLocal() as db:
            try:
                user = await authenticate(db, email=email, password=password)
            except Exception:
                return False

            if not has_permission(user, ADMIN_ACCESS):
                return False

            request.session.update(
                {
                    "admin_user_id": user.id,
                    "admin_email": user.email,
                    "admin_permissions": _serialize_permissions(user),
                }
            )
            return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("admin_user_id")
        if not user_id:
            return False

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User)
                .options(selectinload(User.role).selectinload(Role.permissions))
                .where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user or not user.is_activated or not has_permission(user, ADMIN_ACCESS):
                return False

            request.session.update(
                {
                    "admin_user_id": user.id,
                    "admin_email": user.email,
                    "admin_permissions": _serialize_permissions(user),
                }
            )
            request.state.admin_user = user
            return True
