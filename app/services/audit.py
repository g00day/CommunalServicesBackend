from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import AuditLog, User


def _serialize_details(details: dict[str, Any] | None) -> str | None:
    if not details:
        return None
    return json.dumps(details, ensure_ascii=False, default=str)


async def write_audit_log(
    *,
    action_type: str,
    user: User | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
    commit: bool = False,
) -> None:
    audit_log = AuditLog(
        user_id=user.id if user is not None else user_id,
        user_email=user.email if user is not None else user_email,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=_serialize_details(details),
    )

    if db is not None:
        db.add(audit_log)
        if commit:
            await db.commit()
        return

    async with AsyncSessionLocal() as session:
        session.add(audit_log)
        await session.commit()
