from fastapi import HTTPException

from app.models import User

ADMIN_ACCESS = "admin.access"
USERS_READ = "users.read"
USERS_CREATE = "users.create"
USERS_UPDATE = "users.update"
USERS_DELETE = "users.delete"
ROLES_READ = "roles.read"
ROLES_MANAGE = "roles.manage"
TICKETS_READ_ALL = "tickets.read.all"
TICKETS_UPDATE_STATUS = "tickets.update.status"
TICKETS_DELETE = "tickets.delete"
ADDRESS_MANAGE = "address.manage"
REPORTS_READ = "reports.read"
CHAT_PARTICIPANTS_MANAGE = "chat.participants.manage"


def has_permission(user: User, permission_code: str) -> bool:
    return permission_code in user.permission_codes


def has_any_permission(user: User, *permission_codes: str) -> bool:
    return any(has_permission(user, permission_code) for permission_code in permission_codes)


def require_permission(user: User, permission_code: str, detail: str = "Недостаточно прав") -> None:
    if not has_permission(user, permission_code):
        raise HTTPException(status_code=403, detail=detail)


def require_any_permission(user: User, permission_codes: tuple[str, ...], detail: str = "Недостаточно прав") -> None:
    if not has_any_permission(user, *permission_codes):
        raise HTTPException(status_code=403, detail=detail)
